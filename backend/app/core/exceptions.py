"""自定义异常模块。"""


class AppException(Exception):
    """应用基础异常。"""

    def __init__(self, message: str = "应用内部错误", code: int = -1, status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundException(AppException):
    """资源未找到异常。"""

    def __init__(self, message: str = "资源未找到", code: int = 4041):
        super().__init__(message=message, code=code, status_code=404)


class UnauthorizedException(AppException):
    """未授权异常。"""

    def __init__(self, message: str = "未授权", code: int = 4011):
        super().__init__(message=message, code=code, status_code=401)


class ForbiddenException(AppException):
    """禁止访问异常。"""

    def __init__(self, message: str = "禁止访问", code: int = 4031):
        super().__init__(message=message, code=code, status_code=403)


class ValidationException(AppException):
    """参数校验异常。"""

    def __init__(self, message: str = "参数校验失败", code: int = 4221):
        super().__init__(message=message, code=code, status_code=422)


class ConflictException(AppException):
    """资源冲突异常。"""

    def __init__(self, message: str = "资源冲突", code: int = 4091):
        super().__init__(message=message, code=code, status_code=409)
