from pymongo.errors import OperationFailure

from app.services.rag.answerer import _is_local_vector_search_error


def test_detects_local_mongo_vector_search_failure():
    exc = OperationFailure("$vectorSearch stage is only allowed on MongoDB Atlas")
    assert _is_local_vector_search_error(exc) is True


def test_ignores_other_operation_failures():
    exc = OperationFailure("some other mongo error")
    assert _is_local_vector_search_error(exc) is False
