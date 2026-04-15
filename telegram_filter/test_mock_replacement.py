import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from account_manager import AccountManager
from gui_monitor import FilterThread


class DummySignal:
    def __init__(self):
        self.payloads = []

    def emit(self, payload):
        self.payloads.append(payload)


class FakeFilter:
    def __init__(self, responses):
        self.responses = {name: list(items) for name, items in responses.items()}
        self.manager = None

    async def check_phone(self, phone, country):
        account = self.manager.get_next_account()
        bucket = self.responses.get(account['name'])
        if not bucket:
            raise RuntimeError(f'No fake response configured for {account["name"]}')
        result = dict(bucket.pop(0))
        result.setdefault('original_phone', phone)
        result.setdefault('phone', phone)
        return result


def make_result(registered, state='registered', phone='+10000000000'):
    result = {
        'registered': registered,
        'query_state': state,
        'phone': phone,
        'original_phone': phone,
        'status': 'offline' if registered else None,
        'last_seen': '2026-04-10 12:00:00' if registered else None,
        'error': None if registered else '查询未返回用户'
    }
    if not registered and state == 'query_failed':
        result['error'] = 'query failed'
    return result


def missing_results(count, phone='+15550000001'):
    return [make_result(False, state='empty_result', phone=phone) for _ in range(count)]


def build_manager():
    manager = AccountManager('/Volumes/waijie/tg/telegram_filter/config.json')
    if len(manager.accounts) < 5:
        manager.accounts = []
        manager.role_assignments = {'primary': [], 'backup': []}
        manager.account_stats = {}
        for idx in range(5):
            name = f'acc{idx + 1}'
            account = {
                'name': name,
                'api_id': '0',
                'api_hash': 'fake',
                'phone': f'+1555000000{idx + 1}',
                'proxy': {},
                'client': object(),
                'request_count': 0,
                'last_request_time': None,
                'is_blocked': False,
                'block_until': None,
            }
            manager.accounts.append(account)
            manager.account_stats[name] = {'total_requests': 0, 'errors': 0, 'success': 0}
        manager._initialize_account_roles()
    else:
        for account in manager.accounts:
            account['client'] = object()
            account['is_blocked'] = False
    return manager


async def run_case(case_name, responses):
    manager = build_manager()
    thread = FilterThread([], 'US', {'rate_limit': {'requests_per_account': 30, 'min_delay': 1, 'max_delay': 1}})
    thread.log_signal = DummySignal()
    thread.conflict_signal = DummySignal()
    thread.emergency_pause_signal = DummySignal()
    fake_filter = FakeFilter(responses)

    primary = manager.get_active_primary_accounts()
    result = await thread.handle_account_conflict(
        manager,
        fake_filter,
        primary[0],
        primary[1],
        '+15550000001',
        make_result(True, phone='+15550000001'),
        1,
        1,
    )

    print(f'CASE: {case_name}')
    print('result:', result)
    print('primary:', [(a['name'], a['role'], a['runtime_state']) for a in manager.accounts if a['role'] == 'primary'])
    print('backup:', [(a['name'], a['role'], a['runtime_state']) for a in manager.accounts if a['role'] == 'backup'])
    print('conflicts:', len(thread.conflict_signal.payloads))
    print('emergency:', len(thread.emergency_pause_signal.payloads))
    print('logs:')
    for line in thread.log_signal.payloads:
        print(' ', line)
    print('-' * 40)


async def run_a3_hit_case():
    manager = build_manager()
    thread = FilterThread([], 'US', {'rate_limit': {'requests_per_account': 30, 'min_delay': 1, 'max_delay': 1}})
    thread.log_signal = DummySignal()
    thread.conflict_signal = DummySignal()
    thread.emergency_pause_signal = DummySignal()

    manager.mark_account_suspected(manager.accounts[0], 'miss_before_a3')
    manager.mark_account_suspected(manager.accounts[1], 'miss_before_a3')

    fake_filter = FakeFilter({
        'acc4': [make_result(True, phone='+15550000001')]
    })

    result = await thread.handle_account_conflict(
        manager,
        fake_filter,
        manager.accounts[0],
        manager.accounts[2],
        '+15550000001',
        make_result(True, phone='+15550000001'),
        1,
        1,
    )

    print('CASE: a1+a2 miss, a3 hits')
    print('result:', result)
    print('primary:', [(a['name'], a['role'], a['runtime_state']) for a in manager.accounts if a['role'] == 'primary'])
    print('backup:', [(a['name'], a['role'], a['runtime_state']) for a in manager.accounts if a['role'] == 'backup'])
    print('conflicts:', len(thread.conflict_signal.payloads))
    print('emergency:', len(thread.emergency_pause_signal.payloads))
    print('logs:')
    for line in thread.log_signal.payloads:
        print(' ', line)
    print('-' * 40)


async def main():
    await run_case(
        'b1 replaces a1',
        {
            'acc4': [make_result(True, phone='+15550000001')]
        }
    )

    await run_case(
        'b2 replaces after b1 miss',
        {
            'acc4': missing_results(3),
            'acc5': [make_result(True, phone='+15550000001')]
        }
    )

    await run_case(
        'all fail triggers emergency',
        {
            'acc4': missing_results(3),
            'acc5': missing_results(3),
            'acc2': missing_results(3),
            'acc3': missing_results(3),
        }
    )

    await run_case(
        'partial success emits conflict',
        {
            'acc4': missing_results(3),
            'acc5': missing_results(3),
            'acc2': [make_result(True, phone='+15550000001')],
            'acc3': missing_results(3),
        }
    )

    await run_a3_hit_case()


if __name__ == '__main__':
    asyncio.run(main())
