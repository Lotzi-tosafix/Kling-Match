import ctypes, os

dll = r"C:\Users\user\AppData\Local\Programs\Python\Python312\Lib\site-packages\torch\lib\fbgemm.dll"
try:
    ctypes.CDLL(dll)
    print("OK")
except OSError as e:
    print("Error:", e)

# Try loading the torch lib folder into PATH first
torch_lib = r"C:\Users\user\AppData\Local\Programs\Python\Python312\Lib\site-packages\torch\lib"
os.add_dll_directory(torch_lib)
try:
    ctypes.CDLL(dll)
    print("OK after add_dll_directory")
except OSError as e:
    print("Still error:", e)
