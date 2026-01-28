import os
import subprocess
import platform

class Uad():
    def __init__(self):
        self.inst = None
        # Detect OS for command format
        self.is_windows = platform.system() == "Windows"

    # --- Common Channel ---
    def reset(self):
        cmd = f'{self.inst}.exe com --action reset' if self.is_windows else f'./{self.inst} com --action reset'
        return os.system(cmd)

    def enable(self):
        cmd = f'{self.inst}.exe com --action enable' if self.is_windows else f'./{self.inst} com --action enable'
        return os.system(cmd)

    def disable(self):
        cmd = f'{self.inst}.exe com --action disable' if self.is_windows else f'./{self.inst} com --action disable'
        return os.system(cmd)

    # --- Configuration Channel ---
    def read_CSR(self):
        cmd = f'{self.inst}.exe cfg --address 0x0' if self.is_windows else f'./{self.inst} cfg --address 0x0'
        try:
            csr_bytes = subprocess.check_output(cmd, shell=True)
            return int(csr_bytes, 0)
        except subprocess.CalledProcessError:
            print("error: interface unavailable, cannot read CSR")
            return None

    def read_register(self, address):
        cmd = f'{self.inst}.exe cfg --address {hex(address)}' if self.is_windows else f'./{self.inst} cfg --address {hex(address)}'
        try:
            output = subprocess.check_output(cmd, shell=True)
            return int(output, 0)
        except subprocess.CalledProcessError:
            print(f"error: interface unavailable, cannot read register {hex(address)}")
            return None

    def write_register(self, address, value):
        cmd = f'{self.inst}.exe cfg --address {hex(address)} --data {hex(value)}' if self.is_windows else f'./{self.inst} cfg --address {hex(address)} --data {hex(value)}'
        return os.system(cmd)

    # --- CSR helpers ---
    def is_filter_enabled(self):
        csr = self.read_CSR()
        return (csr >> 0) & 1 if csr is not None else None

    def is_halted(self):
        csr = self.read_CSR()
        return (csr >> 5) & 1 if csr is not None else None

    def buffer_count(self):
        csr = self.read_CSR()
        return (csr >> 8) & 0xFF if csr is not None else None

    def has_overflowed(self):
        csr = self.read_CSR()
        return (csr >> 16) & 1 if csr is not None else None

    # --- HALT functions ---
    def halt(self):
        csr = self.read_CSR()
        if csr is not None:
            csr |= (1 << 5)
            self.write_CSR(csr)

    def write_CSR(self, value):
        cmd = f'{self.inst}.exe cfg --address 0x0 --data {hex(value)}' if self.is_windows else f'./{self.inst} cfg --address 0x0 --data {hex(value)}'
        return os.system(cmd)

    # --- Signal Channel ---
    def drive_signal(self, value):
        cmd = f'{self.inst}.exe sig --data {hex(value)}' if self.is_windows else f'./{self.inst} sig --data {hex(value)}'
        try:
            output_bytes = subprocess.check_output(cmd, shell=True)
            if output_bytes.strip() == b'':
                print(f"Warning: No output returned for input {hex(value)}")
                return None
            return int(output_bytes, 0)
        except subprocess.CalledProcessError:
            print(f"error: interface unavailable, cannot drive signal {hex(value)}")
            return None

# -------------------------------
# Test code
# -------------------------------

test0 = Uad()
test0.inst = "impl0"

# --- Task 1: Enable / Disable Test ---
print("=== Enable/Disable Test ===")
test0.reset()
test0.enable()
enabled = test0.read_register(0x0)
print("Filter enabled:", enabled >> 0 & 1 if enabled is not None else "Cannot read CSR")

test0.disable()
enabled = test0.read_register(0x0)
print("Filter disabled:", enabled >> 0 & 1 if enabled is not None else "Interface unavailable, cannot read CSR")

# --- Task 2: Read/Write Register Test ---
print("\n=== Read/Write Register Test ===")
test0.enable()  # Re-enable to access registers safely

# Read CSR (0x0)
csr_value = test0.read_register(0x0)
print("Initial CSR value:", hex(csr_value) if csr_value is not None else "Cannot read CSR")

# Write a value to COEF register (0x4)
new_coef = 0x12345678
print(f"Writing {hex(new_coef)} to COEF register (0x4)")
test0.write_register(0x4, new_coef)

# Read it back
read_back = test0.read_register(0x4)
print("Read back COEF register:", hex(read_back) if read_back is not None else "Cannot read COEF")

# --- Task 3: Signal Channel ---
print("\n=== Signal Channel Test ===")
test0.enable()  # Make sure filter is enabled
# Optional: unhalt here if you implemented it

inputs = [0x10, 0x20, 0x40, 0x80]
for val in inputs:
    output = test0.drive_signal(val)
    print(f"Input {hex(val)} → Output {hex(output) if output is not None else 'Error'}")

# --- Task 4 Buffer/Halt---
print("\n=== Buffer Test ===")

# Halt the filter so it starts storing inputs in the buffer
test0.halt()
print("Filter halted:", test0.is_halted())

# Define some sample input signals
inputs = [0x10, 0x20, 0x30, 0x40]

# Send inputs one by one and print buffer count
for i, val in enumerate(inputs):
    print(f"Sending input {hex(val)}")
    output = test0.drive_signal(val)  # this will store in buffer since filter is halted
    count = test0.buffer_count()
    print(f"Buffer count after input {i+1}: {count}")
    if test0.has_overflowed():
        print("Uh oh! Buffer overflowed!")

# Clear the buffer
print("Clearing buffer...")
test0.write_CSR(test0.read_CSR() | (1 << 17))  # set IBCLR bit
print("Buffer count after clear:", test0.buffer_count())
print("Overflow after clear:", test0.has_overflowed())

