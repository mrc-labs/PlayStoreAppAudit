"""Qt user interface package."""

from playstore_app_audit.services.installer_source import install_installer_source_extensions
from playstore_app_audit.services.sdk_maintenance import install_sdk_maintenance_filter

install_installer_source_extensions()
install_sdk_maintenance_filter()
