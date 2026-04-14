"""
号码工具模块 - 支持美国号码格式
"""
import re


class PhoneUtils:
    @staticmethod
    def format_us_phone(phone):
        """
        格式化美国手机号
        支持多种输入格式：
        - 1234567890
        - +1234567890
        - +1 234 567 8900
        - (123) 456-7890
        """
        # 移除所有非数字字符
        digits = re.sub(r'\D', '', phone)

        # 如果没有国家码，添加+1
        if len(digits) == 10:
            return f'+1{digits}'
        elif len(digits) == 11 and digits.startswith('1'):
            return f'+{digits}'
        elif phone.startswith('+'):
            return phone
        else:
            return f'+{digits}'

    @staticmethod
    def validate_us_phone(phone):
        """验证美国手机号格式"""
        formatted = PhoneUtils.format_us_phone(phone)
        # 美国号码：+1 + 10位数字
        pattern = r'^\+1\d{10}$'
        return re.match(pattern, formatted) is not None

    @staticmethod
    def format_cn_phone(phone):
        """格式化中国手机号"""
        digits = re.sub(r'\D', '', phone)

        if len(digits) == 11:
            return f'+86{digits}'
        elif len(digits) == 13 and digits.startswith('86'):
            return f'+{digits}'
        elif phone.startswith('+'):
            return phone
        else:
            return f'+{digits}'

    @staticmethod
    def detect_country(phone):
        """检测号码国家"""
        if phone.startswith('+1'):
            return 'US'
        elif phone.startswith('+86'):
            return 'CN'
        elif phone.startswith('+'):
            code = phone[1:4]
            country_codes = {
                '44': 'UK',
                '81': 'JP',
                '82': 'KR',
                '886': 'TW',
                '852': 'HK',
            }
            return country_codes.get(code, 'OTHER')
        return 'UNKNOWN'

    @staticmethod
    def batch_format(phones, country='US'):
        """批量格式化号码"""
        formatted = []
        errors = []

        for phone in phones:
            try:
                if country == 'US':
                    formatted_phone = PhoneUtils.format_us_phone(phone)
                    if PhoneUtils.validate_us_phone(formatted_phone):
                        formatted.append(formatted_phone)
                    else:
                        errors.append(f'{phone} - 格式无效')
                elif country == 'CN':
                    formatted.append(PhoneUtils.format_cn_phone(phone))
                else:
                    formatted.append(phone)
            except Exception as e:
                errors.append(f'{phone} - {str(e)}')

        return formatted, errors
