import pkg_resources


def to_std_dicts(value):
    """Convert nested ordered dicts to normal dicts for better comparison."""
    if isinstance(value, dict):
        return {k: to_std_dicts(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [to_std_dicts(v) for v in value]
    else:
        return value


def is_sqlalchemy_version_less_than(version_string):
    """Check the installed SQLAlchemy version"""
    return pkg_resources.get_distribution('SQLAlchemy').parsed_version < pkg_resources.parse_version(version_string)
