"""Exception classes for the SBEM module."""


class SBEMBaseException(Exception):
    """A base exception for the SBEM module."""

    def __init__(self, message: str):
        """Initialize the exception with a message."""
        self.message = message
        super().__init__(self.message)


class DuplicatesFound(SBEMBaseException):
    """An error raised when duplicates are found in a SBEM component library."""

    def __init__(self, duplicate_field: str):
        """Initialize the exception with a message.

        Args:
            duplicate_field (str): The field with duplicates
        """
        self.duplicate_field = duplicate_field
        self.message = f"Duplicate objects found in library: {duplicate_field}"
        super().__init__(self.message)


class ValueNotFound(SBEMBaseException):
    """An error raised when a value is not found in a SBEM component library."""

    def __init__(self, obj_type: str, value: str):
        """Initialize the exception with a message.

        Args:
            obj_type (str): The type of object that was not found.
            value (str): The value that was not found.
        """
        self.obj_type = obj_type
        self.value = value
        self.message = f"Value not found in library: {obj_type}:{value}"
        super().__init__(self.message)


class NotImplementedParameter(SBEMBaseException):
    """An error raised when a component parameter is not implemented."""

    def __init__(self, parameter_name: str, obj_name: str, obj_type: str):
        """Initialize the exception with a message.

        Args:
            parameter_name (str): The name of the parameter.
            obj_name (str): The name of the object.
            obj_type (str): The type of the object.
        """
        self.parameter_name = parameter_name
        self.obj_name = obj_name
        self.obj_type = obj_type
        self.message = f"Parameter {parameter_name} not implemented for {obj_type.upper()}:{obj_name}"
        super().__init__(self.message)


class ScheduleParseError(SBEMBaseException):
    """An error raised when a schedule cannot be parsed."""

    def __init__(self, schedule_name: str):
        """Initialize the exception with a message.

        Args:
            schedule_name (str): The name of the schedule.
        """
        self.schedule_name = schedule_name
        super().__init__(f"Failed to parse schedule {schedule_name}")


class ScheduleException(SBEMBaseException):
    """An error raised when a schedule cannot be parsed."""

    def __init__(self, schedule_name: str):
        """Initialize the exception with a message.

        Args:
            schedule_name (str): The day schedule

        """
        self.schedule_name = schedule_name
        self.message = f"Failed to parse schedule {schedule_name}"
        super().__init__(self.message)


class SBEMBuilderNotImplementedError(NotImplementedError):
    """Raised when a parameter is not yet implemented in the SBEM shoebox builder."""

    def __init__(self, parameter: str):
        """Initialize the error.

        Args:
            parameter (str): The parameter that is not yet implemented.
        """
        self.parameter = parameter
        super().__init__(
            f"Parameter {parameter} is not yet implemented in the SBEM shoebox builder."
        )
