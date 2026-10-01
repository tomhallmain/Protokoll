class AppInfo:
    SERVICE_NAME = "MyPersonalApplicationsService"
    APP_IDENTIFIER = "protokoll"
    #: Identifiers this app has used before. Key material is filed per
    #: identifier, so a rename orphans the old keys and everything encrypted
    #: under them -- an old name listed here keeps scripts/key_material.py
    #: reporting and backing it up. Empty: this app has never been renamed.
    LEGACY_APP_IDENTIFIERS = ()
    #: The service name apps in this family derive their log encryption key
    #: under, each with its own app identifier. Separate from SERVICE_NAME so
    #: that its <SERVICE>_PASSPHRASE env-var override answers for the log key
    #: alone. A tracker can name a different one for an app that does not follow this.
    LOG_ENCRYPTION_SERVICE = "MyPersonalApplicationsServiceLogs"
