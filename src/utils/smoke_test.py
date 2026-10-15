"""``run.py --smoke-test [--expect-oqs]``: checks a built executable works, without a window.

``isolate_environment()`` runs before any other app import, because loggers,
the config dir and the key store resolve their paths from the environment as
modules load. It points every per-user location at a scratch directory and
gives the run its own key store identity with passphrases from the
environment, so the run touches neither the user's data, the OS keyring, nor
an external drive. A separate identity also keeps the key store migration
from moving (and deleting) any leftover keychain items of the real one.
Imports nothing from the app at load time: build_exe.py runs this file on its
own to build the same environment.
"""

#: Key store identity for the run; never one a real install uses.
SMOKE_SERVICE_NAME = "ProtokollSmokeTest"
SMOKE_LOG_SERVICE_NAME = "ProtokollSmokeTestLogs"
SMOKE_APP_IDENTIFIER = "smoke_test"
#: Set to keep the scratch directory at a known place (build_exe.py does).
SCRATCH_DIR_ENV = "PROTOKOLL_SMOKE_DIR"


def passphrase_env_var(service_name: str) -> str:
    """The variable PassphraseManager reads a service's passphrase from."""
    return f"{service_name.upper()}_PASSPHRASE"


def smoke_test_environment(scratch: str) -> dict:
    """Every variable the run sets, all pointing into *scratch*. Assigned over
    the inherited values, so a variable exported in the developer's shell
    cannot reach the real locations."""
    import os
    import secrets

    home = os.path.join(scratch, "home")
    return {
        "HOME": home,
        "USERPROFILE": home,
        "APPDATA": os.path.join(scratch, "appdata"),
        "LOCALAPPDATA": os.path.join(scratch, "localappdata"),
        "XDG_DATA_HOME": os.path.join(scratch, "data"),
        "PROTOKOLL_CACHE_DIR": os.path.join(scratch, "cache"),
        "PROTOKOLL_KEY_BACKUP_DIR": os.path.join(scratch, "key_backup"),
        passphrase_env_var(SMOKE_SERVICE_NAME): secrets.token_hex(16),
        passphrase_env_var(SMOKE_LOG_SERVICE_NAME): secrets.token_hex(16),
        "QT_QPA_PLATFORM": "offscreen",
        SCRATCH_DIR_ENV: scratch,
    }


def isolate_environment() -> str:
    """Apply smoke_test_environment() to this process and switch AppInfo to the
    smoke identity; returns the scratch directory. SCRATCH_DIR_ENV names it,
    otherwise a new temp directory is used."""
    import os
    import tempfile

    from .globals import AppInfo

    scratch = os.environ.get(SCRATCH_DIR_ENV) or tempfile.mkdtemp(prefix="protokoll-smoke-")
    os.environ.update(smoke_test_environment(scratch))
    AppInfo.SERVICE_NAME = SMOKE_SERVICE_NAME
    AppInfo.LOG_ENCRYPTION_SERVICE = SMOKE_LOG_SERVICE_NAME
    AppInfo.APP_IDENTIFIER = SMOKE_APP_IDENTIFIER
    return scratch


class SmokeTest:
    """The checks, each logged on one line and run under guarded(), so one
    failure still lets the others report."""

    def __init__(self, scratch: str):
        from .logging_setup import get_logger

        self.scratch = scratch
        self.failures = []
        self._app = None
        self.logger = get_logger("smoke_test")

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.logger.info(f"smoke test: {name}: {'ok' if ok else 'FAILED'} {detail}".rstrip())
        if not ok:
            self.failures.append(name)

    def guarded(self, name: str, func) -> None:
        """Run the check *func*; anything it raises, SystemExit included (a
        bundled package without metadata exits the process on a version
        probe), fails *name* with its full traceback."""
        import traceback

        try:
            func()
        except BaseException:
            self.logger.error(f"smoke test: {name}: FAILED\n{traceback.format_exc()}")
            self.failures.append(name)

    def result(self) -> int:
        """Exit code: 0 if every check passed."""
        if self.failures:
            self.logger.error(f"smoke test failed: {', '.join(self.failures)}")
            return 1
        self.logger.info("smoke test passed")
        return 0

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def check_bundled_files(self) -> None:
        import glob
        import os

        from .app_paths import IS_BUILD, resource_path
        from .translations import I18N
        from .version import VERSION_FILE, app_version, build_info

        catalogs = glob.glob(os.path.join(I18N.localedir, "*", "LC_MESSAGES", "base.mo"))
        self.check("locale", bool(catalogs), f"{len(catalogs)} catalog(s) in {I18N.localedir}")
        self.check("VERSION", os.path.isfile(resource_path(VERSION_FILE)), app_version())
        if IS_BUILD:
            recorded = build_info().get("version")
            self.check("build info", recorded == app_version(), f"records version {recorded}")
        else:
            self.logger.info("smoke test: build info: not checked in a source checkout")

    def check_config(self) -> None:
        import os

        from .config_manager import ConfigManager

        config = ConfigManager()
        config.save_config()
        self.check("config", os.path.isfile(config.config_file), str(config.config_file))

    def check_keyring_backend(self) -> None:
        import keyring
        import keyring.backends.fail

        backend = keyring.get_keyring()
        self.check(
            "keyring backend",
            not isinstance(backend, keyring.backends.fail.Keyring),
            f"{type(backend).__module__}.{type(backend).__name__}",
        )

    def check_encrypted_cache(self) -> None:
        """Keys generated and the cache stored and read back, under the smoke identity."""
        import os

        from .app_info_cache import AppInfoCache
        from .encryptor import get_encryptor, read_key_store
        from .globals import AppInfo

        service, app_id = AppInfo.SERVICE_NAME, AppInfo.APP_IDENTIFIER
        if service != SMOKE_SERVICE_NAME:
            raise RuntimeError(f"Refusing to create keys outside the smoke identity: {service}:{app_id}")
        # The encryptor counts an environment passphrase as keys having existed,
        # so it refuses to generate them for an empty key store; force_new is its
        # deliberate way to start one. Only with no store, so nothing is purged.
        if read_key_store(service, app_id) is None:
            get_encryptor(service, app_id).generate_and_store_keys(service, app_id, force_new=True)

        directory = os.path.join(self.scratch, "cache_check")
        os.makedirs(directory, exist_ok=True)
        cache = AppInfoCache.for_directory(directory)
        cache.set("smoke_test", "round trip")
        encrypted = cache.store()
        AppInfoCache.clear_instances()
        reloaded = AppInfoCache.for_directory(directory)
        self.check(
            "encrypted cache",
            encrypted and reloaded.load_error is None and reloaded.get("smoke_test") == "round trip",
            "" if encrypted else "stored as plain JSON, encryption failed",
        )

    def check_encrypted_log(self) -> None:
        import os

        from .encryptor import StreamingLogCipher
        from .file_handler import FileHandler
        from .globals import AppInfo

        service, app_id = AppInfo.LOG_ENCRYPTION_SERVICE, SMOKE_APP_IDENTIFIER
        key = StreamingLogCipher.find_key(service, app_id)
        path = os.path.join(self.scratch, "smoke.log.enc")
        with open(path, "wb") as f:
            f.write(StreamingLogCipher.encrypt_record(key, b"encrypted smoke line\n"))
        success, content, _info = FileHandler().read_file_safe(path, key_candidates=[(service, app_id)])
        self.check("encrypted log", success and "encrypted smoke line" in content)

    def check_compressed_logs(self) -> None:
        import bz2
        import gzip
        import os
        import zipfile

        from .file_handler import FileHandler

        line = b"compressed smoke line\n"
        handler = FileHandler()
        for name in ("smoke.log.gz", "smoke.log.bz2", "smoke.log.zip"):
            path = os.path.join(self.scratch, name)
            if name.endswith(".zip"):
                with zipfile.ZipFile(path, "w") as archive:
                    archive.writestr("smoke.log", line)
            else:
                compress = gzip.compress if name.endswith(".gz") else bz2.compress
                with open(path, "wb") as f:
                    f.write(compress(line))
            success, content, _info = handler.read_file_safe(path)
            self.check(f"compressed log ({name.rsplit('.', 1)[-1]})",
                       success and "compressed smoke line" in content)

    def check_encoding_detection(self) -> None:
        import chardet

        detected = chardet.detect("Grüße aus dem Rauchtest, äöü ÄÖÜ ß".encode("latin-1"))
        self.check("chardet", bool(detected.get("encoding")), str(detected.get("encoding")))

    def check_oqs(self, expect_oqs: bool) -> None:
        from . import encryptor

        available = encryptor.KeyEncapsulation is not None
        if expect_oqs:
            self.check("OQS key encapsulation", available)
        else:
            self.logger.info(
                f"smoke test: OQS key encapsulation {'available' if available else 'not in this build'}")

    def check_process_list(self) -> None:
        """The old-build cleanup removes nothing off Windows, and relies on the
        rename alone on Windows, when it cannot list running processes."""
        from .unpack_cleanup import _running_executables

        executables = _running_executables()
        self.check("process list", executables is not None,
                   "" if executables is None else f"{len(executables)} executable(s)")

    def check_fault_log(self) -> None:
        import os

        from .crash_log import enable_fault_log

        path = enable_fault_log()
        self.check("fault log", os.path.isfile(path), path)

    def _qt_app(self):
        """The QApplication, created on first use and kept for the rest of the
        run: PyQt destroys one nothing references, and an event loop without
        it never delivers a worker thread's signal."""
        from PyQt6.QtWidgets import QApplication

        if self._app is None:
            self._app = QApplication.instance() or QApplication([])
        return self._app

    def check_qt(self) -> None:
        """A QApplication, Qt's messages reaching the log, the window icon
        readable, and the main window created and closed (offscreen)."""
        from PyQt6.QtGui import QImage

        from ..ui.main_window import MainWindow
        from ..ui.qt_message_log import qt_message_reaches_logging
        from .app_paths import ICON_FILE, resource_path
        from .theme_manager import ThemeManager

        app = self._qt_app()
        self.check("Qt messages logged", qt_message_reaches_logging())
        # A missing file or a build without Qt's ICO image plugin shows no
        # icon and raises nothing; reading it here catches both.
        icon_path = resource_path(ICON_FILE)
        self.check("window icon", not QImage(icon_path).isNull(), icon_path)
        ThemeManager.apply_dark_theme(app)
        window = MainWindow()
        window.close()
        window.deleteLater()
        self.check("main window", True)

    def check_qt_thread(self) -> None:
        """A log read on a LogLoadThread, its result delivered back to this
        thread through a queued signal, as the viewer receives every load and
        search. Nuitka's PyQt6 plugin warns that Qt threading may not work."""
        import os

        from PyQt6.QtCore import QEventLoop, QTimer

        from ..ui.log_workers import LogLoadThread

        self._qt_app()
        path = os.path.join(self.scratch, "thread.log")
        with open(path, "w", encoding="utf-8") as f:
            f.write("thread smoke line\n")
        results = []
        loop = QEventLoop()

        def loaded(_generation, result):
            results.append(result)
            loop.quit()

        worker = LogLoadThread(1, path, 1024 * 1024, [])
        worker.loaded.connect(loaded)
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(loop.quit)
        timeout.start(10000)
        worker.start()
        loop.exec()
        timeout.stop()
        finished = worker.wait(5000)
        result = results[0] if results else None
        self.check("Qt worker thread",
                   finished and result is not None and result.success
                   and "thread smoke line" in result.content,
                   "" if results else "no result within 10s")


def run_smoke_test(scratch: str, expect_oqs: bool = False) -> int:
    """Run every check; returns the exit code."""
    smoke = SmokeTest(scratch)
    smoke.logger.info(f"smoke test: scratch directory {scratch}")
    smoke.guarded("bundled files", smoke.check_bundled_files)
    smoke.guarded("config", smoke.check_config)
    smoke.guarded("keyring backend", smoke.check_keyring_backend)
    smoke.guarded("encrypted cache", smoke.check_encrypted_cache)
    smoke.guarded("encrypted log", smoke.check_encrypted_log)
    smoke.guarded("compressed logs", smoke.check_compressed_logs)
    smoke.guarded("chardet", smoke.check_encoding_detection)
    smoke.guarded("OQS key encapsulation", lambda: smoke.check_oqs(expect_oqs))
    smoke.guarded("process list", smoke.check_process_list)
    smoke.guarded("fault log", smoke.check_fault_log)
    smoke.guarded("Qt", smoke.check_qt)
    smoke.guarded("Qt worker thread", smoke.check_qt_thread)
    return smoke.result()
