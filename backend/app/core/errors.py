class ApiError(Exception):
    """A controlled API error that keeps error responses consistent."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
