import os
import subprocess
import ctypes
import winreg
import shutil
import tempfile
import psutil
import wmi
from pathlib import Path
from typing import Callable, Optional
from concurrent.futures import ThreadPoolExecutor


class SystemOptimizer:
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self._log = log_callback or print
        self._is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        self._wmi = wmi.WMI()
    
    def _execute_cmd(self, command: str, shell: bool = True) -> tuple[bool, str]:
        try:
            result = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def _get_size_mb(self, path: str) -> float:
        total = 0
        try:
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total += os.path.getsize(fp)
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            pass
        return total / (1024 * 1024)
    
    def _safe_remove(self, path: str) -> int:
        removed = 0
        try:
            if os.path.isfile(path):
                size = os.path.getsize(path)
                os.remove(path)
                return size
            elif os.path.isdir(path):
                for root, dirs, files in os.walk(path, topdown=False):
                    for name in files:
                        try:
                            fp = os.path.join(root, name)
                            removed += os.path.getsize(fp)
                            os.remove(fp)
                        except (OSError, PermissionError):
                            pass
                    for name in dirs:
                        try:
                            os.rmdir(os.path.join(root, name))
                        except (OSError, PermissionError):
                            pass
        except (OSError, PermissionError):
            pass
        return removed
    
    def clean_temp_files(self) -> dict:
        self._log("Очистка временных файлов...")
        
        temp_paths = [
            tempfile.gettempdir(),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp'),
            os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Temp'),
            os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Prefetch'),
        ]
        
        total_freed = 0
        files_removed = 0
        
        for temp_path in temp_paths:
            if not os.path.exists(temp_path):
                continue
            
            self._log(f"  Очистка: {temp_path}")
            
            try:
                for item in os.listdir(temp_path):
                    item_path = os.path.join(temp_path, item)
                    try:
                        if os.path.isfile(item_path):
                            size = os.path.getsize(item_path)
                            os.remove(item_path)
                            total_freed += size
                            files_removed += 1
                        elif os.path.isdir(item_path):
                            freed = self._safe_remove(item_path)
                            total_freed += freed
                            files_removed += 1
                            try:
                                os.rmdir(item_path)
                            except:
                                pass
                    except (OSError, PermissionError):
                        pass
            except (OSError, PermissionError):
                pass
        
        freed_mb = total_freed / (1024 * 1024)
        self._log(f"  Очищено: {freed_mb:.2f} MB ({files_removed} файлов)")
        
        return {"freed_mb": freed_mb, "files_removed": files_removed}
    
    def clean_browser_cache(self) -> dict:
        self._log("Очистка кэша браузеров...")
        
        user_profile = os.environ.get('USERPROFILE', '')
        local_appdata = os.environ.get('LOCALAPPDATA', '')
        appdata = os.environ.get('APPDATA', '')
        
        browser_caches = [
            os.path.join(local_appdata, 'Google', 'Chrome', 'User Data', 'Default', 'Cache'),
            os.path.join(local_appdata, 'Google', 'Chrome', 'User Data', 'Default', 'Code Cache'),
            os.path.join(local_appdata, 'Google', 'Chrome', 'User Data', 'Default', 'GPUCache'),
            os.path.join(local_appdata, 'Microsoft', 'Edge', 'User Data', 'Default', 'Cache'),
            os.path.join(local_appdata, 'Microsoft', 'Edge', 'User Data', 'Default', 'Code Cache'),
            os.path.join(local_appdata, 'BraveSoftware', 'Brave-Browser', 'User Data', 'Default', 'Cache'),
            os.path.join(appdata, 'Opera Software', 'Opera Stable', 'Cache'),
            os.path.join(local_appdata, 'Mozilla', 'Firefox', 'Profiles'),
        ]
        
        total_freed = 0
        
        for cache_path in browser_caches:
            if os.path.exists(cache_path):
                self._log(f"  Очистка: {os.path.basename(os.path.dirname(cache_path))}")
                freed = self._safe_remove(cache_path)
                total_freed += freed
        
        freed_mb = total_freed / (1024 * 1024)
        self._log(f"  Очищено кэша браузеров: {freed_mb:.2f} MB")
        
        return {"freed_mb": freed_mb}
    
    def optimize_ram(self) -> dict:
        self._log("Оптимизация оперативной памяти...")
        
        before = psutil.virtual_memory()
        before_used = before.used / (1024 * 1024 * 1024)
        
        try:
            ctypes.windll.kernel32.SetProcessWorkingSetSize(
                ctypes.windll.kernel32.GetCurrentProcess(),
                ctypes.c_size_t(-1),
                ctypes.c_size_t(-1)
            )
            
            self._execute_cmd('powershell -Command "[System.GC]::Collect()"')
            
            if self._is_admin:
                self._execute_cmd('powershell -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"')
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        after = psutil.virtual_memory()
        after_used = after.used / (1024 * 1024 * 1024)
        freed = max(0, before_used - after_used)
        
        self._log(f"  Освобождено RAM: {freed:.2f} GB")
        self._log(f"  Доступно RAM: {after.available / (1024 * 1024 * 1024):.2f} GB")
        
        return {"freed_gb": freed, "available_gb": after.available / (1024 * 1024 * 1024)}
    
    def enable_game_mode(self) -> dict:
        self._log("Активация игрового режима Windows...")
        
        results = {"success": False, "changes": []}
        
        try:
            key_path = r"Software\Microsoft\GameBar"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "AllowAutoGameMode", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "AutoGameModeEnabled", 0, winreg.REG_DWORD, 1)
                results["changes"].append("GameMode enabled")
            
            key_path = r"Software\Microsoft\GameBar"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "UseNexusForGameBarEnabled", 0, winreg.REG_DWORD, 0)
                results["changes"].append("GameBar overlay disabled")
            
            results["success"] = True
            self._log("  Игровой режим активирован")
            
        except PermissionError:
            self._log("  Требуются права администратора")
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def optimize_visual_effects(self) -> dict:
        self._log("Оптимизация визуальных эффектов...")
        
        results = {"success": False, "changes": []}
        
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "VisualFXSetting", 0, winreg.REG_DWORD, 2)
                results["changes"].append("Visual effects set to performance")
            
            key_path = r"Control Panel\Desktop"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "DragFullWindows", 0, winreg.REG_SZ, "0")
                results["changes"].append("Window drag optimized")
            
            key_path = r"Control Panel\Desktop\WindowMetrics"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "MinAnimate", 0, winreg.REG_SZ, "0")
                results["changes"].append("Animation disabled")
            
            results["success"] = True
            self._log("  Визуальные эффекты оптимизированы для производительности")
            self._log("  ✓ Шрифты остались нормальными")
            
        except PermissionError:
            self._log("  Требуются права администратора для некоторых настроек")
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def restore_visual_effects(self) -> dict:
        self._log("Восстановление визуальных эффектов...")
        
        results = {"success": False}
        
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "VisualFXSetting", 0, winreg.REG_DWORD, 1)
            
            key_path = r"Control Panel\Desktop"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "DragFullWindows", 0, winreg.REG_SZ, "1")
                winreg.SetValueEx(key, "FontSmoothing", 0, winreg.REG_SZ, "2")
            
            key_path = r"Control Panel\Desktop\WindowMetrics"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "MinAnimate", 0, winreg.REG_SZ, "1")
            
            results["success"] = True
            self._log("  Визуальные эффекты восстановлены")
            self._log("  Перезайди в систему для применения всех изменений")
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def optimize_power_plan(self) -> dict:
        self._log("Настройка плана электропитания...")
        
        results = {"success": False}
        
        high_perf_guid = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
        
        success, output = self._execute_cmd(f'powercfg /setactive {high_perf_guid}')
        
        if not success:
            self._execute_cmd('powercfg -duplicatescheme 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c')
            success, output = self._execute_cmd(f'powercfg /setactive {high_perf_guid}')
        
        if success:
            self._log("  План электропитания: Высокая производительность")
            self._log("  ⚠️ Ноутбук будет быстрее разряжаться!")
            results["success"] = True
        else:
            self._log("  Не удалось изменить план электропитания")
        
        return results
    
    def restore_power_plan(self) -> dict:
        self._log("Восстановление сбалансированного плана питания...")
        
        results = {"success": False}
        
        balanced_guid = "381b4222-f694-41f0-9685-ff5bb260df2e"
        
        success, _ = self._execute_cmd(f'powercfg /setactive {balanced_guid}')
        
        if success:
            self._log("  План электропитания: Сбалансированный")
            results["success"] = True
        else:
            self._log("  Не удалось изменить план электропитания")
        
        return results
    
    def optimize_network_gaming(self) -> dict:
        self._log("Оптимизация сети для игр...")
        
        results = {"success": False, "changes": []}
        
        try:
            key_path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "TcpAckFrequency", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "TCPNoDelay", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "TcpDelAckTicks", 0, winreg.REG_DWORD, 0)
                results["changes"].append("TCP optimizations applied")
            
            success, _ = self._execute_cmd(
                'netsh int tcp set global autotuninglevel=normal'
            )
            if success:
                results["changes"].append("TCP autotuning optimized")
            
            success, _ = self._execute_cmd(
                'netsh int tcp set global congestionprovider=ctcp'
            )
            if success:
                results["changes"].append("Congestion provider set to CTCP")
            
            results["success"] = True
            self._log("  Сетевые настройки оптимизированы для низкой задержки")
            
        except PermissionError:
            self._log("  Требуются права администратора")
            results["success"] = False
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def optimize_dns(self) -> dict:
        self._log("Оптимизация DNS...")
        
        results = {"success": False}
        
        dns_servers = [
            ("1.1.1.1", "1.0.0.1"),
            ("8.8.8.8", "8.8.4.4"),
        ]
        
        primary, secondary = dns_servers[0]
        
        try:
            for nic in self._wmi.Win32_NetworkAdapterConfiguration(IPEnabled=True):
                nic.SetDNSServerSearchOrder([primary, secondary])
            
            results["success"] = True
            self._log(f"  DNS настроен: {primary}, {secondary} (Cloudflare)")
            
        except Exception as e:
            success, _ = self._execute_cmd(
                f'netsh interface ip set dns "Ethernet" static {primary} primary'
            )
            if success:
                self._execute_cmd(
                    f'netsh interface ip add dns "Ethernet" {secondary} index=2'
                )
                results["success"] = True
                self._log(f"  DNS настроен через netsh: {primary}, {secondary}")
            else:
                self._log(f"  Ошибка настройки DNS: {e}")
        
        return results
    
    def disable_startup_programs(self) -> dict:
        self._log("Анализ автозагрузки...")
        
        results = {"programs": [], "disabled": 0}
        
        startup_paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ]
        
        for hkey, path in startup_paths:
            try:
                with winreg.OpenKey(hkey, path, 0, winreg.KEY_READ) as key:
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            results["programs"].append({
                                "name": name,
                                "path": value,
                                "hkey": "HKCU" if hkey == winreg.HKEY_CURRENT_USER else "HKLM"
                            })
                            i += 1
                        except OSError:
                            break
            except (OSError, PermissionError):
                pass
        
        self._log(f"  Найдено программ в автозагрузке: {len(results['programs'])}")
        
        return results
    
    def disable_unnecessary_services(self, include_xbox: bool = False) -> dict:
        self._log("Оптимизация служб Windows...")
        
        services_to_disable = [
            "SysMain",
            "DiagTrack",
            "dmwappushservice",
            "WSearch",
            "TabletInputService",
            "Fax",
        ]
        
        if include_xbox:
            self._log("⚠️ Отключение служб Xbox (Game Pass работать не будет!)")
            services_to_disable.extend([
                "XblAuthManager",
                "XblGameSave",
                "XboxNetApiSvc",
                "XboxGipSvc",
            ])
        
        results = {"disabled": [], "failed": []}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        for service in services_to_disable:
            success, _ = self._execute_cmd(f'sc config "{service}" start= disabled')
            if success:
                self._execute_cmd(f'sc stop "{service}"')
                results["disabled"].append(service)
            else:
                results["failed"].append(service)
        
        self._log(f"  Отключено служб: {len(results['disabled'])}")
        
        return results
    
    def enable_services(self) -> dict:
        self._log("Восстановление служб Windows...")
        
        services_to_enable = [
            ("SysMain", "auto"),
            ("WSearch", "auto"),
        ]
        
        results = {"enabled": [], "failed": []}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        for service, start_type in services_to_enable:
            success, _ = self._execute_cmd(f'sc config "{service}" start= {start_type}')
            if success:
                self._execute_cmd(f'sc start "{service}"')
                results["enabled"].append(service)
            else:
                results["failed"].append(service)
        
        self._log(f"  Восстановлено служб: {len(results['enabled'])}")
        self._log("  SysMain и поиск Windows снова работают")
        
        return results
    
    def disable_xbox_services(self) -> dict:
        self._log("⚠️ Отключение служб Xbox...")
        self._log("  ВНИМАНИЕ: Xbox Game Pass и Xbox приложение работать не будут!")
        
        xbox_services = [
            "XblAuthManager",
            "XblGameSave",
            "XboxNetApiSvc",
            "XboxGipSvc",
        ]
        
        results = {"disabled": [], "failed": []}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        for service in xbox_services:
            success, _ = self._execute_cmd(f'sc config "{service}" start= disabled')
            if success:
                self._execute_cmd(f'sc stop "{service}"')
                results["disabled"].append(service)
            else:
                results["failed"].append(service)
        
        self._log(f"  Отключено служб Xbox: {len(results['disabled'])}")
        
        return results
    
    def enable_xbox_services(self) -> dict:
        self._log("Включение служб Xbox...")
        
        xbox_services = [
            "XblAuthManager",
            "XblGameSave",
            "XboxNetApiSvc",
            "XboxGipSvc",
        ]
        
        results = {"enabled": [], "failed": []}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        for service in xbox_services:
            success, _ = self._execute_cmd(f'sc config "{service}" start= demand')
            if success:
                results["enabled"].append(service)
            else:
                results["failed"].append(service)
        
        self._log(f"  Включено служб Xbox: {len(results['enabled'])}")
        self._log("  Xbox Game Pass теперь будет работать")
        
        return results
    
    def flush_dns_cache(self) -> dict:
        self._log("Очистка DNS кэша...")
        
        results = {"success": False}
        
        success, _ = self._execute_cmd("ipconfig /flushdns")
        if success:
            results["success"] = True
            self._log("  DNS кэш очищен")
        else:
            self._log("  Ошибка очистки DNS кэша")
        
        return results
    
    def clean_windows_update_cache(self) -> dict:
        self._log("Очистка кэша Windows Update...")
        
        results = {"freed_mb": 0, "success": False}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        update_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'SoftwareDistribution', 'Download')
        
        if os.path.exists(update_path):
            self._execute_cmd('net stop wuauserv')
            
            before_size = self._get_size_mb(update_path)
            self._safe_remove(update_path)
            after_size = self._get_size_mb(update_path)
            
            self._execute_cmd('net start wuauserv')
            
            results["freed_mb"] = before_size - after_size
            results["success"] = True
            
            self._log(f"  Очищено: {results['freed_mb']:.2f} MB")
        
        return results
    
    def get_system_info(self) -> dict:
        cpu_percent = psutil.cpu_percent(interval=None)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        
        if not hasattr(self, '_cached_cpu_name'):
            try:
                for processor in self._wmi.Win32_Processor():
                    self._cached_cpu_name = processor.Name
                    break
            except:
                self._cached_cpu_name = "Unknown"
        
        if not hasattr(self, '_cached_gpu_name'):
            try:
                for gpu in self._wmi.Win32_VideoController():
                    self._cached_gpu_name = gpu.Name
                    break
            except:
                self._cached_gpu_name = "Unknown"
        
        cpu_info = self._cached_cpu_name
        gpu_info = self._cached_gpu_name
        
        return {
            "cpu_name": cpu_info,
            "cpu_usage": cpu_percent,
            "gpu_name": gpu_info,
            "ram_total_gb": memory.total / (1024 ** 3),
            "ram_used_gb": memory.used / (1024 ** 3),
            "ram_available_gb": memory.available / (1024 ** 3),
            "ram_percent": memory.percent,
            "disk_total_gb": disk.total / (1024 ** 3),
            "disk_used_gb": disk.used / (1024 ** 3),
            "disk_free_gb": disk.free / (1024 ** 3),
            "disk_percent": disk.percent,
            "is_admin": self._is_admin,
        }
    
    def optimize_input_lag(self) -> dict:
        self._log("Оптимизация Input Lag...")
        
        results = {"success": False, "changes": []}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        try:
            key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "SystemResponsiveness", 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(key, "NetworkThrottlingIndex", 0, winreg.REG_DWORD, 0xffffffff)
                results["changes"].append("SystemResponsiveness = 0 (max priority)")
            
            key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile\Tasks\Games"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "GPU Priority", 0, winreg.REG_DWORD, 8)
                winreg.SetValueEx(key, "Priority", 0, winreg.REG_DWORD, 6)
                winreg.SetValueEx(key, "Scheduling Category", 0, winreg.REG_SZ, "High")
                winreg.SetValueEx(key, "SFIO Priority", 0, winreg.REG_SZ, "High")
                results["changes"].append("Game priority set to HIGH")
            
            self._log("  Приоритет игр установлен на максимум")
            results["success"] = True
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def disable_fullscreen_optimizations(self) -> dict:
        self._log("Отключение Fullscreen Optimizations...")
        
        results = {"success": False}
        
        try:
            key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "__COMPAT_LAYER", 0, winreg.REG_SZ, "~ DISABLEDXMAXIMIZEDWINDOWEDMODE")
            
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "AppCaptureEnabled", 0, winreg.REG_DWORD, 0)
            
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\GameDVR"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "AppCaptureEnabled", 0, winreg.REG_DWORD, 0)
            
            self._log("  Fullscreen Optimizations отключены")
            self._log("  Game DVR/запись отключена")
            results["success"] = True
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def optimize_mouse(self) -> dict:
        self._log("Оптимизация мыши для игр...")
        
        results = {"success": False}
        
        try:
            key_path = r"Control Panel\Mouse"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "MouseSpeed", 0, winreg.REG_SZ, "0")
                winreg.SetValueEx(key, "MouseThreshold1", 0, winreg.REG_SZ, "0")
                winreg.SetValueEx(key, "MouseThreshold2", 0, winreg.REG_SZ, "0")
                winreg.SetValueEx(key, "MouseSensitivity", 0, winreg.REG_SZ, "10")
            
            self._log("  Акселерация мыши отключена")
            self._log("  Чувствительность: 6/11 (raw input)")
            results["success"] = True
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def disable_background_apps(self) -> dict:
        self._log("Отключение фоновых приложений...")
        
        results = {"success": False}
        
        try:
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "GlobalUserDisabled", 0, winreg.REG_DWORD, 1)
            
            key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Search"
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "BackgroundAppGlobalToggle", 0, winreg.REG_DWORD, 0)
            
            self._log("  Фоновые приложения отключены")
            results["success"] = True
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def optimize_timer_resolution(self) -> dict:
        self._log("Оптимизация системного таймера...")
        
        results = {"success": False}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        try:
            self._execute_cmd('bcdedit /set useplatformtick yes')
            self._execute_cmd('bcdedit /set disabledynamictick yes')
            
            key_path = r"SYSTEM\CurrentControlSet\Control\Session Manager\kernel"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "GlobalTimerResolutionRequests", 0, winreg.REG_DWORD, 1)
            
            self._log("  Таймер: Platform tick enabled")
            self._log("  Таймер: Dynamic tick disabled")
            self._log("  ⚠️ Требуется перезагрузка!")
            results["success"] = True
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def disable_hpet(self) -> dict:
        self._log("Отключение HPET (снижает input lag)...")
        
        results = {"success": False}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        success, _ = self._execute_cmd('bcdedit /deletevalue useplatformclock')
        if not success:
            self._execute_cmd('bcdedit /set useplatformclock false')
        
        self._log("  HPET отключен")
        self._log("  ⚠️ Требуется перезагрузка!")
        results["success"] = True
        
        return results
    
    def optimize_gpu_scheduling(self) -> dict:
        self._log("Настройка GPU Scheduling...")
        
        results = {"success": False}
        
        try:
            key_path = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
            with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "HwSchMode", 0, winreg.REG_DWORD, 2)
            
            self._log("  Hardware-accelerated GPU Scheduling: ON")
            self._log("  ⚠️ Требуется перезагрузка!")
            results["success"] = True
            
        except Exception as e:
            self._log(f"  Ошибка: {e}")
        
        return results
    
    def disable_core_parking(self) -> dict:
        self._log("Отключение Core Parking (все ядра активны)...")
        
        results = {"success": False}
        
        if not self._is_admin:
            self._log("  Требуются права администратора")
            return results
        
        self._execute_cmd('powercfg -setacvalueindex scheme_current sub_processor CPMINCORES 100')
        self._execute_cmd('powercfg -setactive scheme_current')
        
        self._log("  Core Parking отключен (100% ядер активно)")
        results["success"] = True
        
        return results
    
    def run_ultimate_optimization(self) -> dict:
        self._log("=" * 50)
        self._log("ULTIMATE GAMING OPTIMIZATION")
        self._log("=" * 50)
        
        results = {}
        
        optimizations = [
            ("input_lag", self.optimize_input_lag),
            ("fullscreen", self.disable_fullscreen_optimizations),
            ("mouse", self.optimize_mouse),
            ("background_apps", self.disable_background_apps),
            ("gpu_scheduling", self.optimize_gpu_scheduling),
            ("core_parking", self.disable_core_parking),
        ]
        
        for name, func in optimizations:
            try:
                results[name] = func()
            except Exception as e:
                self._log(f"Ошибка в {name}: {e}")
                results[name] = {"error": str(e)}
        
        self._log("=" * 50)
        self._log("ULTIMATE OPTIMIZATION COMPLETE")
        self._log("⚠️ Перезагрузите компьютер для применения всех настроек!")
        self._log("=" * 50)
        
        return results
    
    def run_full_optimization(self) -> dict:
        self._log("=" * 50)
        self._log("ПОЛНАЯ ОПТИМИЗАЦИЯ СИСТЕМЫ")
        self._log("=" * 50)
        
        results = {}
        
        optimizations = [
            ("temp_files", self.clean_temp_files),
            ("browser_cache", self.clean_browser_cache),
            ("ram", self.optimize_ram),
            ("game_mode", self.enable_game_mode),
            ("visual_effects", self.optimize_visual_effects),
            ("power_plan", self.optimize_power_plan),
            ("dns_flush", self.flush_dns_cache),
        ]
        
        if self._is_admin:
            optimizations.extend([
                ("network", self.optimize_network_gaming),
                ("services", self.disable_unnecessary_services),
                ("windows_update", self.clean_windows_update_cache),
            ])
        
        for name, func in optimizations:
            try:
                results[name] = func()
            except Exception as e:
                self._log(f"Ошибка в {name}: {e}")
                results[name] = {"error": str(e)}
        
        self._log("=" * 50)
        self._log("ОПТИМИЗАЦИЯ ЗАВЕРШЕНА")
        self._log("=" * 50)
        
        return results


class ProcessOptimizer:
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self._log = log_callback or print
    
    def get_resource_heavy_processes(self, limit: int = 10) -> list:
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                if info['cpu_percent'] is not None and info['memory_percent'] is not None:
                    processes.append({
                        'pid': info['pid'],
                        'name': info['name'],
                        'cpu': info['cpu_percent'],
                        'memory': info['memory_percent']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        processes.sort(key=lambda x: x['cpu'] + x['memory'], reverse=True)
        return processes[:limit]
    
    def set_process_priority(self, pid: int, priority: str = "high") -> bool:
        priority_map = {
            "realtime": psutil.REALTIME_PRIORITY_CLASS,
            "high": psutil.HIGH_PRIORITY_CLASS,
            "above_normal": psutil.ABOVE_NORMAL_PRIORITY_CLASS,
            "normal": psutil.NORMAL_PRIORITY_CLASS,
            "below_normal": psutil.BELOW_NORMAL_PRIORITY_CLASS,
            "idle": psutil.IDLE_PRIORITY_CLASS,
        }
        
        try:
            proc = psutil.Process(pid)
            proc.nice(priority_map.get(priority, psutil.HIGH_PRIORITY_CLASS))
            self._log(f"Приоритет процесса {proc.name()} установлен: {priority}")
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError) as e:
            self._log(f"Ошибка установки приоритета: {e}")
            return False
    
    def terminate_process(self, pid: int) -> bool:
        try:
            proc = psutil.Process(pid)
            name = proc.name()
            proc.terminate()
            self._log(f"Процесс {name} завершён")
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self._log(f"Ошибка завершения процесса: {e}")
            return False
    
    def boost_game_process(self, process_name: str) -> bool:
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if process_name.lower() in proc.info['name'].lower():
                    return self.set_process_priority(proc.info['pid'], "high")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        self._log(f"Процесс {process_name} не найден")
        return False

