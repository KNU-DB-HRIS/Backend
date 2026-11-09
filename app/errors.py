from flask import current_app, jsonify
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    def __init__(self, code, status=422, message=None, details=None):
        self.code, self.status = code, status
        self.message, self.details = message or code, details or {}
        super().__init__(self.message)


def register_errors(app):
    @app.errorhandler(ApiError)
    def api_error(error):
        return jsonify(
            error={"code": error.code, "message": error.message, "details": error.details}
        ), error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        codes = {
            400: "BAD_REQUEST",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            413: "FILE_TOO_LARGE",
            415: "UNSUPPORTED_MEDIA_TYPE",
        }
        return api_error(ApiError(codes.get(error.code, "HTTP_ERROR"), error.code))

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        current_app.logger.error("Database operation failed: %s", type(error).__name__)
        return api_error(ApiError("DATABASE_ERROR", 503, "데이터베이스 요청을 처리할 수 없습니다"))

    @app.errorhandler(Exception)
    def unexpected_error(error):
        current_app.logger.error("Request failed: %s", type(error).__name__)
        return api_error(ApiError("INTERNAL_ERROR", 500, "요청을 처리할 수 없습니다"))
