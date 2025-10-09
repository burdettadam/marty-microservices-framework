"""Configuration-related exceptions for the Marty Framework."""


class ConfigurationError(Exception):
    """Raised when there's an issue with configuration."""

    pass


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration is invalid."""

    pass


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""

    pass
