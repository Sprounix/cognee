from cognee.exceptions import CogneeApiError
from fastapi import status


class UnstructuredLibraryImportError(CogneeApiError):
    def __init__(
        self,
        message: str = "Import error. Unstructured library is not installed.",
        name: str = "UnstructuredModuleImportError",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    ):
        super().__init__(message, name, status_code)


class UnauthorizedDataAccessError(CogneeApiError):
    def __init__(
        self,
        message: str = "User does not have permission to access this data.",
        name: str = "UnauthorizedDataAccessError",
        status_code=status.HTTP_401_UNAUTHORIZED,
    ):
        super().__init__(message, name, status_code)


class DatasetNotFoundError(CogneeApiError):
    def __init__(
        self,
        message: str = "Dataset not found.",
        name: str = "DatasetNotFoundError",
        status_code=status.HTTP_404_NOT_FOUND,
    ):
        super().__init__(message, name, status_code)


class DatasetTypeError(CogneeApiError):
    def __init__(
        self,
        message: str = "Dataset type not supported.",
        name: str = "DatasetTypeError",
        status_code=status.HTTP_400_BAD_REQUEST,
    ):
        super().__init__(message, name, status_code)
