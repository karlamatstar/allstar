from __future__ import annotations

import ctypes
import os


ERROR_ALREADY_EXISTS = 183
DUPLICATE_INSTANCE_EXIT_CODE = 23


class SingleInstanceLock:
    """Windows 이름 있는 뮤텍스로 프로그램의 중복 실행을 막는다."""

    def __init__(self, name: str, kernel32=None):
        self.name = name
        self._kernel32 = kernel32
        self._handle = None

    def acquire(self) -> bool:
        if os.name != "nt" and self._kernel32 is None:
            # AllStar 컨트롤러는 Windows 전용이다. 다른 환경의 코드 검사에서는
            # GUI 실행을 막지 않고 통과시킨다.
            self._handle = True
            return True

        kernel32 = self._kernel32 or ctypes.WinDLL("kernel32", use_last_error=True)
        if self._kernel32 is None:
            kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.restype = ctypes.c_bool

        if hasattr(ctypes, "set_last_error"):
            ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())

        last_error = (
            kernel32.get_last_error()
            if hasattr(kernel32, "get_last_error")
            else ctypes.get_last_error()
        )
        if last_error == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False

        self._kernel32 = kernel32
        self._handle = handle
        return True

    def release(self) -> None:
        if self._handle in (None, True):
            self._handle = None
            return
        self._kernel32.CloseHandle(self._handle)
        self._handle = None

    def __enter__(self) -> "SingleInstanceLock":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.release()
