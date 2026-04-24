"""号池 - 整个反封控架构的唯一真相来源。

职责：
- 账号四态机（warmup/active/cooling/retired）+ 健康分
- 日配额硬截断（按号龄）
- 代理 provider 指纹绑定（§5.6）
- Sticky session 强制（§5.7）
- 子网/provider 多样性选号（§5.9）
- API 调用计数（§5.3 多样化的数据源）
- FloodWait 24h 滑窗熔断（§5.5）
- PEER_FLOOD 立即退役（§5.12）
- 联系人簿日清计数（§5.10）
- 状态持久化到 account_state.json（与 config.json 分离）

不做：实际的网络请求、代理建立、Telegram client 创建 —— 这些由
account_manager / filter 调用 pool 的接口拿到指令后自己执行。
"""
import hashlib
import json
import os
import random
import re
import threading
import time
import zlib
from collections import Counter
from datetime import datetime
from typing import Optional

try:
    import pytz
    _US_EASTERN = pytz.timezone('America/New_York')
except ImportError:
    _US_EASTERN = None


# ---------- 状态常量 ----------
STATE_WARMUP = 'warmup'
STATE_ACTIVE = 'active'
STATE_COOLING = 'cooling'
STATE_RETIRED = 'retired'

# ---------- 退役原因 ----------
RETIRE_FLOODWAIT_ACCUM = 'floodwait_accumulated'
RETIRE_FLOODWAIT_LONG = 'floodwait_long'
RETIRE_PEER_FLOOD = 'peer_flood'
RETIRE_SPAM_WAIT = 'spam_wait'
RETIRE_DEACTIVATED = 'deactivated'
RETIRE_MANUAL = 'manual'

# 永久限制错误码（§5.12）—— 触发即退役，不走累计
PERMANENT_LIMIT_CODES = (
    'PEER_FLOOD',
    'SPAM_WAIT',
    'USER_PRIVACY_RESTRICTED',
    'USER_DEACTIVATED',
    'USER_DEACTIVATED_BAN',
    'AUTH_KEY_UNREGISTERED',
    'SESSION_REVOKED',
)


# ---------- 并发公式（§0）----------
def default_concurrency(n):
    """N 越大，并发占比越小，分散 IP 聚簇风险。"""
    if n <= 0:
        return 0
    if n <= 5:
        return max(1, n)
    if n <= 20:
        return max(4, n // 4)
    if n <= 100:
        return max(6, n // 8)
    return max(10, n // 12)


# ---------- 日配额（§5.11）----------
def daily_quota(age_days):
    """按号龄返回今日配额上限。"""
    if age_days < 3:
        return 25
    if age_days < 7:
        return 50
    if age_days < 14:
        return 80
    if age_days < 30:
        return 120
    return 150


# ---------- 代理指纹 / Sticky ----------
_REGION_RE = re.compile(r'-(?:region|country|zone|geo)-([A-Za-z]{2,3})', re.IGNORECASE)
_SESSION_RE = re.compile(r'-(?:session|sid|sess)-([A-Za-z0-9]+)', re.IGNORECASE)


def _extract_region(user):
    if not user:
        return ''
    m = _REGION_RE.search(user)
    return (m.group(1).upper() if m else '')


def _extract_sub_user_prefix(user):
    """去掉 session/region/sid 动态段，保留账号前缀。"""
    if not user:
        return ''
    s = re.sub(r'-(?:session|sid|sess)-[A-Za-z0-9]+', '', user, flags=re.IGNORECASE)
    s = re.sub(r'-(?:region|country|zone|geo)-[A-Za-z]{2,3}', '', s, flags=re.IGNORECASE)
    s = re.sub(r'-(?:sticky|t)-\d+', '', s, flags=re.IGNORECASE)
    return s.strip('-').strip()


def provider_fingerprint(proxy):
    """根据代理 dict 生成 provider 指纹（IP / 端口 / session 变化不影响）。"""
    if not proxy or not proxy.get('host'):
        return ''
    host = (proxy.get('host') or '').lower().strip()
    # 去掉最前段数字 IP 部分，只看域名主体
    if any(c.isalpha() for c in host):
        host_domain = host
    else:
        host_domain = host  # 纯 IP 就保留
    region = _extract_region(proxy.get('username') or '')
    prefix = _extract_sub_user_prefix(proxy.get('username') or '')
    raw = f"{host_domain}|{region}|{prefix}"
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]


def build_sticky_proxy_user(account_name, base_user):
    """自动注入 -session-<crc32(name)>，同一号每次启动拿同一出口 IP。"""
    if not base_user:
        return base_user
    if '-session-' in base_user or '-sid-' in base_user or '-sess-' in base_user:
        return base_user
    sid = f"{zlib.crc32(account_name.encode('utf-8')):08x}"
    return f"{base_user}-session-{sid}"


def build_sticky_proxy_for(account, base_proxy):
    """给单账号构造带 sticky session 的代理 dict。输入 base_proxy，输出新 dict。"""
    if not base_proxy or not base_proxy.get('host'):
        return None
    sticky_user = build_sticky_proxy_user(
        account.get('name') or '',
        base_proxy.get('username') or '',
    )
    return {
        'host': base_proxy['host'],
        'port': int(base_proxy.get('port') or 1080),
        'username': sticky_user,
        'password': base_proxy.get('password') or '',
    }


# ---------- 时区降频（§5.15）----------
def is_us_quiet_hour():
    """美东 02:00-07:00 降频时段。"""
    if _US_EASTERN is None:
        return False
    try:
        h = datetime.now(_US_EASTERN).hour
        return 2 <= h < 7
    except Exception:
        return False


# ---------- 默认状态 / 配置 ----------
def _new_state_entry(name, first_login_ts=None):
    return {
        'name': name,
        'first_login_ts': first_login_ts or int(time.time()),
        'state': STATE_ACTIVE,
        'health_score': 80,
        'total_requests': 0,
        'total_success': 0,
        'today_date': '',
        'today_requests': 0,
        'today_success': 0,
        'today_api_calls': {},      # {'ImportContactsRequest': 42, ...}
        'today_contacts_reset': 0,
        'today_empty_returns': 0,
        'consecutive_empty': 0,
        'floodwait_events': [],     # 24h 滑窗内的时间戳
        'last_used_ts': 0,
        'last_check_ts': 0,
        'cooling_until_ts': 0,
        'cooling_reason': '',
        'retired_reason': '',
        'bound_proxy_fingerprint': '',
        'source_type': 'session',   # 'session' | 'tdata'
    }


DEFAULT_POOL_CONFIG = {
    'max_concurrency': None,
    'warmup_hours': 72,
    'floodwait_retire_threshold': 3,
    'floodwait_window_hours': 24,
    'floodwait_retire_seconds': 300,
    'cooling_min_minutes': 20,
    'cooling_max_minutes': 60,
    'per_account_daily_quota_default': 50,
    'health_retire_threshold': 10,
    'health_cooling_threshold': 30,
    'empty_probe_threshold': 30,
    'pacing': {
        'burst_min': 2, 'burst_max': 4,
        'burst_interval_min': 8, 'burst_interval_max': 18,
        'quiet_interval_min': 180, 'quiet_interval_max': 600,
        'quiet_hour_multiplier': 3.0,
    },
    'decoy_call_interval': 12,
    'force_daily_contacts_reset': True,
    'tdata_health_bonus': 10,
    'dc1_lock': False,
    'check_cache_hours': 24,
}


# ---------- 持久化 ----------
def _atomic_write_json(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _today_date():
    """返回美东日期字符串 YYYY-MM-DD，与 §5.11 "跨日 00:00" 对应。"""
    if _US_EASTERN is not None:
        try:
            return datetime.now(_US_EASTERN).strftime('%Y-%m-%d')
        except Exception:
            pass
    return datetime.now().strftime('%Y-%m-%d')


class AccountPool:
    """号池。所有账号状态读写的唯一入口，线程安全。"""

    def __init__(self, config_path, state_path=None):
        self.config_path = config_path
        self.state_path = state_path or os.path.join(
            os.path.dirname(os.path.abspath(config_path)), 'account_state.json'
        )
        self._lock = threading.RLock()
        self._load()

    # ---------- 加载 / 保存 ----------
    def _load(self):
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.pool_config = {**DEFAULT_POOL_CONFIG,
                            **(self.config.get('pool_config') or {})}
        # 深合并 pacing
        pacing = {**DEFAULT_POOL_CONFIG['pacing'],
                  **(self.pool_config.get('pacing') or {})}
        self.pool_config['pacing'] = pacing

        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
            except Exception:
                self.state = {}
        else:
            self.state = {}

        self._migrate()
        self._rollover_if_new_day()

    def _migrate(self):
        """老用户首次启用：给所有已有账号补默认 state。"""
        for acc in self.config.get('accounts', []):
            name = acc.get('name')
            if not name:
                continue
            if name not in self.state:
                # 用 session 文件 mtime 估算 first_login
                first_ts = int(time.time())
                try:
                    from account_manager import _get_session_path
                    sp = _get_session_path(name) + '.session'
                    if os.path.exists(sp):
                        first_ts = int(os.path.getmtime(sp))
                except Exception:
                    pass
                entry = _new_state_entry(name, first_login_ts=first_ts)
                # tdata 源账号起始分 +bonus（§5.13）
                if acc.get('source_type') == 'tdata':
                    entry['source_type'] = 'tdata'
                    entry['health_score'] = min(
                        100, entry['health_score'] + self.pool_config.get('tdata_health_bonus', 10)
                    )
                self.state[name] = entry
            else:
                # 补新字段，兼容老 state.json
                default = _new_state_entry(name)
                for k, v in default.items():
                    self.state[name].setdefault(k, v)
        self._save_nolock()

    def _rollover_if_new_day(self):
        today = _today_date()
        changed = False
        for name, entry in self.state.items():
            if entry.get('today_date') != today:
                entry['today_date'] = today
                entry['today_requests'] = 0
                entry['today_success'] = 0
                entry['today_api_calls'] = {}
                entry['today_contacts_reset'] = 0
                entry['today_empty_returns'] = 0
                # 跨日配额重置，附赠健康分 +5（§5.11 奖励自律）
                entry['health_score'] = min(100, entry['health_score'] + 5)
                # 如果因配额达标被冷却，跨日自动回 active
                if entry['state'] == STATE_COOLING and entry.get('cooling_reason') == 'quota_exhausted':
                    entry['state'] = STATE_ACTIVE
                    entry['cooling_until_ts'] = 0
                    entry['cooling_reason'] = ''
                changed = True
        if changed:
            self._save_nolock()

    def _save_nolock(self):
        _atomic_write_json(self.state_path, self.state)

    def save(self):
        with self._lock:
            self._save_nolock()

    # ---------- 查询接口 ----------
    def get_entry(self, name):
        with self._lock:
            return self.state.get(name)

    def age_days(self, name):
        entry = self.state.get(name)
        if not entry:
            return 0
        return max(0, int((time.time() - entry['first_login_ts']) / 86400))

    def _auto_transition(self, name):
        """根据时间自动转状态：warmup→active（72h后）、cooling→active（到期后）。"""
        entry = self.state.get(name)
        if not entry:
            return
        now = time.time()
        # warmup 到期
        if entry['state'] == STATE_WARMUP:
            warmup_sec = self.pool_config['warmup_hours'] * 3600
            if now - entry['first_login_ts'] >= warmup_sec:
                entry['state'] = STATE_ACTIVE
        # cooling 到期
        if entry['state'] == STATE_COOLING and entry['cooling_until_ts']:
            if now >= entry['cooling_until_ts']:
                # 跨日配额冷却只有跨日才解除
                if entry.get('cooling_reason') != 'quota_exhausted':
                    entry['state'] = STATE_ACTIVE
                    entry['cooling_until_ts'] = 0
                    entry['cooling_reason'] = ''

    def _quota_exhausted(self, name):
        entry = self.state.get(name)
        if not entry:
            return True
        quota = daily_quota(self.age_days(name))
        return entry['today_requests'] >= quota

    def compute_concurrency(self):
        """K = f(N)，允许 config 覆盖。只数 active 号。"""
        with self._lock:
            self._tick_all()
            active = [n for n, e in self.state.items() if e['state'] == STATE_ACTIVE]
            n_active = len(active)
            override = self.pool_config.get('max_concurrency')
            if override:
                try:
                    override = int(override)
                    return min(override, n_active)
                except (TypeError, ValueError):
                    pass
            return min(default_concurrency(n_active), n_active)

    def get_active_batch(self, k=None, exclude_subnets=True):
        """返回 k 个最适合筛号的账号名（不含 entry 对象，只名字）。"""
        with self._lock:
            self._tick_all()
            if k is None:
                k = self.compute_concurrency()
            candidates = []
            for name, entry in self.state.items():
                if entry['state'] != STATE_ACTIVE:
                    continue
                if self._quota_exhausted(name):
                    # 到配额的自动冷却到次日
                    self._mark_cooling_nolock(name, reason='quota_exhausted', next_day=True)
                    continue
                candidates.append((name, entry))

            # 排序：健康分降序、上次使用升序
            candidates.sort(
                key=lambda t: (-t[1]['health_score'], t[1]['last_used_ts'])
            )

            if not exclude_subnets:
                return [n for n, _ in candidates[:k]]

            # 代理 provider 去重（§5.9）
            chosen = []
            used_fps = set()
            for name, entry in candidates:
                fp = entry.get('bound_proxy_fingerprint') or ''
                if fp and fp in used_fps:
                    continue
                chosen.append(name)
                if fp:
                    used_fps.add(fp)
                if len(chosen) >= k:
                    break
            # 兜底：如果严格去重后不够，补齐
            if len(chosen) < k:
                for name, _ in candidates:
                    if name not in chosen:
                        chosen.append(name)
                        if len(chosen) >= k:
                            break
            return chosen

    def get_by_state(self, state):
        with self._lock:
            return [n for n, e in self.state.items() if e['state'] == state]

    def get_health_snapshot(self):
        with self._lock:
            self._tick_all()
            rows = []
            for name, entry in self.state.items():
                age = self.age_days(name)
                rows.append({
                    'name': name,
                    'state': entry['state'],
                    'health': entry['health_score'],
                    'age_days': age,
                    'today_requests': entry['today_requests'],
                    'today_success': entry['today_success'],
                    'today_quota': daily_quota(age),
                    'total_requests': entry['total_requests'],
                    'floodwait_24h': len(self._prune_floodwait(entry)),
                    'last_used_ts': entry['last_used_ts'],
                    'cooling_until_ts': entry['cooling_until_ts'],
                    'cooling_reason': entry.get('cooling_reason', ''),
                    'retired_reason': entry.get('retired_reason', ''),
                    'bound_proxy_fingerprint': entry.get('bound_proxy_fingerprint', ''),
                    'source_type': entry.get('source_type', 'session'),
                })
            return rows

    def summary(self):
        """给日志打的总览。"""
        counts = Counter()
        with self._lock:
            for entry in self.state.values():
                counts[entry['state']] += 1
            total = sum(counts.values())
            k = self.compute_concurrency()
        return {
            'total': total,
            'active': counts[STATE_ACTIVE],
            'warmup': counts[STATE_WARMUP],
            'cooling': counts[STATE_COOLING],
            'retired': counts[STATE_RETIRED],
            'concurrency_k': k,
        }

    # ---------- FloodWait 滑窗 ----------
    def _prune_floodwait(self, entry):
        win_sec = self.pool_config['floodwait_window_hours'] * 3600
        cutoff = time.time() - win_sec
        entry['floodwait_events'] = [t for t in entry['floodwait_events'] if t > cutoff]
        return entry['floodwait_events']

    # ---------- 健康分重算 ----------
    def _recalc_health(self, name):
        entry = self.state.get(name)
        if not entry:
            return
        score = 100
        fw_24h = len(self._prune_floodwait(entry))
        score -= fw_24h * 15
        # 空返比
        if entry['today_requests'] > 0:
            ratio = entry['today_empty_returns'] / entry['today_requests']
            score -= int(ratio * 40)
        # 预热期扣分
        now = time.time()
        warmup_sec = self.pool_config['warmup_hours'] * 3600
        if now - entry['first_login_ts'] < warmup_sec:
            score -= 20
        # 今日成功数加成，封顶 +10
        score += min(entry['today_success'], 50) // 5
        entry['health_score'] = max(0, min(100, score))

        # 阈值触发状态转换
        if entry['health_score'] < self.pool_config['health_retire_threshold']:
            self._mark_retired_nolock(name, reason='health_below_threshold')
        elif entry['health_score'] < self.pool_config['health_cooling_threshold']:
            if entry['state'] == STATE_ACTIVE:
                self._mark_cooling_nolock(name, reason='health_low')

    # ---------- tick ----------
    def _tick_all(self):
        for name in list(self.state.keys()):
            self._auto_transition(name)
        self._rollover_if_new_day()

    def tick(self):
        """外部定时器调，每 30s 一次即可。"""
        with self._lock:
            self._tick_all()
            for name in list(self.state.keys()):
                self._recalc_health(name)
            self._save_nolock()

    # ---------- 状态更新（对外）----------
    def record_request(self, name, success=True, api_name=None):
        with self._lock:
            entry = self.state.get(name)
            if not entry:
                return
            entry['total_requests'] += 1
            entry['today_requests'] += 1
            entry['last_used_ts'] = int(time.time())
            if success:
                entry['total_success'] += 1
                entry['today_success'] += 1
                entry['consecutive_empty'] = 0
            if api_name:
                entry['today_api_calls'][api_name] = \
                    entry['today_api_calls'].get(api_name, 0) + 1
            # 配额达标 → 冷却到次日
            if self._quota_exhausted(name):
                self._mark_cooling_nolock(name, reason='quota_exhausted', next_day=True)
            self._save_nolock()

    def record_empty_return(self, name):
        with self._lock:
            entry = self.state.get(name)
            if not entry:
                return
            entry['today_empty_returns'] += 1
            entry['consecutive_empty'] += 1
            threshold = self.pool_config.get('empty_probe_threshold', 30)
            if entry['consecutive_empty'] >= threshold:
                self._mark_cooling_nolock(name, reason='empty_probe_threshold')
                entry['consecutive_empty'] = 0
            self._save_nolock()

    def record_floodwait(self, name, seconds):
        with self._lock:
            entry = self.state.get(name)
            if not entry:
                return
            entry['floodwait_events'].append(time.time())
            self._prune_floodwait(entry)
            # 单次超阈值直接退役
            if seconds >= self.pool_config['floodwait_retire_seconds']:
                self._mark_retired_nolock(name, reason=RETIRE_FLOODWAIT_LONG)
                self._save_nolock()
                return
            # 滑窗累计超阈值 → 退役
            if len(entry['floodwait_events']) >= self.pool_config['floodwait_retire_threshold']:
                self._mark_retired_nolock(name, reason=RETIRE_FLOODWAIT_ACCUM)
            else:
                # 单次 FW → 短冷却，时长 = fw seconds + 抖动
                cool = max(60, int(seconds)) + random.randint(30, 120)
                self._mark_cooling_nolock(name, reason='floodwait', duration_sec=cool)
            self._save_nolock()

    def record_permanent_limit(self, name, code):
        """§5.12 PEER_FLOOD 等立即退役。"""
        reason_map = {
            'PEER_FLOOD': RETIRE_PEER_FLOOD,
            'SPAM_WAIT': RETIRE_SPAM_WAIT,
            'USER_DEACTIVATED': RETIRE_DEACTIVATED,
            'USER_DEACTIVATED_BAN': RETIRE_DEACTIVATED,
            'AUTH_KEY_UNREGISTERED': RETIRE_DEACTIVATED,
            'SESSION_REVOKED': RETIRE_DEACTIVATED,
        }
        with self._lock:
            self._mark_retired_nolock(name, reason=reason_map.get(code, code.lower()))
            self._save_nolock()

    def record_contacts_reset(self, name):
        with self._lock:
            entry = self.state.get(name)
            if not entry:
                return
            entry['today_contacts_reset'] += 1
            self._save_nolock()

    def needs_daily_contacts_reset(self, name):
        with self._lock:
            entry = self.state.get(name)
            if not entry:
                return False
            if not self.pool_config.get('force_daily_contacts_reset'):
                return False
            return entry['today_contacts_reset'] == 0

    def needs_decoy_call(self, name):
        """每 N 次真筛号插一次伪装调用。"""
        interval = self.pool_config.get('decoy_call_interval', 12)
        if interval <= 0:
            return False
        with self._lock:
            entry = self.state.get(name)
            if not entry:
                return False
            n = entry['today_requests']
            return n > 0 and n % interval == 0

    def api_distribution(self, name):
        with self._lock:
            entry = self.state.get(name)
            if not entry:
                return {}
            total = sum(entry['today_api_calls'].values()) or 1
            return {api: cnt / total for api, cnt in entry['today_api_calls'].items()}

    # ---------- 状态转换（内部 nolock）----------
    def _mark_cooling_nolock(self, name, reason='', duration_sec=None, next_day=False):
        entry = self.state.get(name)
        if not entry or entry['state'] == STATE_RETIRED:
            return
        if next_day:
            # 冷到次日 00:00 美东
            from datetime import timedelta
            now = time.time()
            if _US_EASTERN is not None:
                try:
                    dt = datetime.now(_US_EASTERN)
                    tomorrow = dt.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    entry['cooling_until_ts'] = int(tomorrow.timestamp())
                except Exception:
                    entry['cooling_until_ts'] = int(now + 6 * 3600)
            else:
                entry['cooling_until_ts'] = int(now + 6 * 3600)
        else:
            if duration_sec is None:
                mn = self.pool_config['cooling_min_minutes']
                mx = self.pool_config['cooling_max_minutes']
                duration_sec = random.randint(mn * 60, mx * 60)
            entry['cooling_until_ts'] = int(time.time() + duration_sec)
        entry['state'] = STATE_COOLING
        entry['cooling_reason'] = reason

    def mark_cooling(self, name, duration_sec=None, reason=''):
        with self._lock:
            self._mark_cooling_nolock(name, reason=reason, duration_sec=duration_sec)
            self._save_nolock()

    def _mark_retired_nolock(self, name, reason=''):
        entry = self.state.get(name)
        if not entry:
            return
        entry['state'] = STATE_RETIRED
        entry['retired_reason'] = reason

    def mark_retired(self, name, reason=''):
        with self._lock:
            self._mark_retired_nolock(name, reason)
            self._save_nolock()

    def mark_warmup(self, name):
        with self._lock:
            entry = self.state.get(name)
            if entry:
                entry['state'] = STATE_WARMUP
                self._save_nolock()

    def mark_active(self, name, reason='manual_reactivate'):
        with self._lock:
            entry = self.state.get(name)
            if not entry:
                return
            entry['state'] = STATE_ACTIVE
            entry['cooling_until_ts'] = 0
            entry['cooling_reason'] = ''
            entry['retired_reason'] = ''
            self._save_nolock()

    # ---------- 代理绑定（§5.6）----------
    def bind_proxy(self, name, proxy):
        """返回 (changed, severity, msg)。severity: 'ok'|'yellow'|'red'。"""
        with self._lock:
            entry = self.state.get(name)
            if not entry:
                return False, 'ok', ''
            new_fp = provider_fingerprint(proxy)
            old_fp = entry.get('bound_proxy_fingerprint') or ''
            if not old_fp:
                entry['bound_proxy_fingerprint'] = new_fp
                self._save_nolock()
                return True, 'ok', 'first_bind'
            if old_fp == new_fp:
                return False, 'ok', 'same'
            # 不同：判定严重程度
            severity, msg = self._proxy_change_severity(entry, proxy)
            entry['bound_proxy_fingerprint'] = new_fp
            self._save_nolock()
            return True, severity, msg

    def _proxy_change_severity(self, entry, new_proxy):
        old_region = entry.get('_last_region', '')
        new_region = _extract_region(new_proxy.get('username') or '')
        if old_region and new_region and old_region != new_region:
            return 'red', f'region changed {old_region}→{new_region}'
        entry['_last_region'] = new_region
        return 'yellow', 'provider changed'

    # ---------- check 缓存（§M2）----------
    def is_check_fresh(self, name):
        with self._lock:
            entry = self.state.get(name)
            if not entry or not entry.get('last_check_ts'):
                return False
            hours = self.pool_config.get('check_cache_hours', 24)
            return (time.time() - entry['last_check_ts']) < hours * 3600

    def mark_checked(self, name):
        with self._lock:
            entry = self.state.get(name)
            if entry:
                entry['last_check_ts'] = int(time.time())
                self._save_nolock()

    # ---------- 账号增删 ----------
    def register_account(self, name, source_type='session', first_login_ts=None):
        """批量导入时调用，新号默认进 warmup。"""
        with self._lock:
            if name in self.state:
                return
            entry = _new_state_entry(name, first_login_ts=first_login_ts)
            entry['state'] = STATE_WARMUP
            entry['source_type'] = source_type
            if source_type == 'tdata':
                entry['health_score'] = min(
                    100, entry['health_score'] + self.pool_config.get('tdata_health_bonus', 10)
                )
            self.state[name] = entry
            self._save_nolock()

    def remove_account(self, name):
        with self._lock:
            self.state.pop(name, None)
            self._save_nolock()
