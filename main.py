import os
import subprocess
import platform

# -------------------------------
# UAD class to interface with IP
# -------------------------------
class Uad():
    def __init__(self):
        self.inst = None
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
            return int(csr_bytes.strip(), 16)
        except subprocess.CalledProcessError:
            print("error: interface unavailable, cannot read CSR")
            return None

    def read_register(self, address):
        cmd = f'{self.inst}.exe cfg --address {hex(address)}' if self.is_windows else f'./{self.inst} cfg --address {hex(address)}'
        try:
            output = subprocess.check_output(cmd, shell=True)
            return int(output.strip(), 16)
        except subprocess.CalledProcessError:
            print(f"error: interface unavailable, cannot read register {hex(address)}")
            return None

    def write_register(self, address, value):
        cmd = f'{self.inst}.exe cfg --address {hex(address)} --data {hex(value)}' if self.is_windows else f'./{self.inst} cfg --address {hex(address)} --data {hex(value)}'
        return os.system(cmd)

    def write_CSR(self, value):
        cmd = f'{self.inst}.exe cfg --address 0x0 --data {hex(value)}' if self.is_windows else f'./{self.inst} cfg --address 0x0 --data {hex(value)}'
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

    # --- Signal Channel ---
    def drive_signal(self, value):
        cmd = f'{self.inst}.exe sig --data {hex(value)}' if self.is_windows else f'./{self.inst} sig --data {hex(value)}'
        try:
            output = subprocess.check_output(cmd, shell=True)
            output = output.strip()
            if not output:
                # No output returned
                return None
            return int(output, 16)
        except subprocess.CalledProcessError:
            print(f"error: interface unavailable, cannot drive signal {hex(value)}")
            return None
        except ValueError:
            print(f"error: invalid output from signal command: {output}")
            return None

# -------------------------------
# Test functions
# -------------------------------
def enable_disable_test(uad):
    print("=== Enable/Disable Test ===")
    uad.reset()
    uad.enable()
    csr = uad.read_CSR()
    if csr is not None:
        print(f"CSR after enable: 0x{csr:08X}")
        print("Filter enabled:", (csr >> 0) & 1)
    else:
        print("CSR after enable: Interface unavailable")
        print("Filter enabled: Interface unavailable")
    uad.disable()
    csr = uad.read_CSR()
    if csr is not None:
        print(f"CSR after disable: 0x{csr:08X}")
        print("Filter enabled:", (csr >> 0) & 1)
    else:
        print("CSR after disable: Interface unavailable")
        print("Filter enabled: Interface unavailable")

def bypass_test(uad):
    print("\n=== Filter Bypass Test ===")
    
    # Ensure filter enabled initially
    uad.enable()  # FEN=1, HALT=0

    # Input sequence
    inputs = [0x10, 0x20, 0x40, 0x80, 0x01, 0x02, 0x04, 0x08]

    # --- Bypass ON: disable filter (FEN=0) ---
    csr = uad.read_CSR()
    if csr is not None:
        uad.write_CSR(csr & ~(1 << 0))  # FEN=0
        print("Bypass mode activated (FEN=0)")

    print("\n-- Sending signals with Bypass ON --")
    for val in inputs:
        output = uad.drive_signal(val)
        print(f"Input {hex(val)} → Output {hex(output) if output is not None else 'Error'}")

    # --- Bypass OFF: enable filter (FEN=1) ---
    csr = uad.read_CSR()
    if csr is not None:
        uad.write_CSR((csr | (1 << 0)) & ~(1 << 5))  # FEN=1, HALT=0
        print("\nBypass mode deactivated (FEN=1, HALT cleared)")

    # Flush FIR pipeline
    for _ in range(4):
        uad.drive_signal(0x0)

    print("\n-- Sending signals with Bypass OFF --")
    for val in inputs:
        output = uad.drive_signal(val)
        print(f"Input {hex(val)} → Output {hex(output) if output is not None else 'Error'}")



def buffer_halt_test(uad):
    print("\n=== Task 4: Buffer/Halt/Overflow Test ===")
    uad.halt()
    print("Filter halted:", uad.is_halted())
    # Clear buffer
    uad.write_CSR(uad.read_CSR() | (1 << 17))  # IBCLR
    print("Buffer cleared → Buffer count:", uad.buffer_count())
    print("Overflow after clear:", uad.has_overflowed())
    # Send some inputs
    inputs = [0x10, 0x20, 0x30, 0x40]
    for i, val in enumerate(inputs):
        uad.drive_signal(val)
        count = uad.buffer_count()
        print(f"Input {i+1} ({hex(val)}) sent → Buffer count: {count}")
        if uad.has_overflowed():
            print("Unexpected overflow detected!")
    # Overflow test
    print("\n-- Testing buffer overflow safely --")
    for i in range(260):
        uad.drive_signal(0x10)
        count = uad.buffer_count()
        if i % 50 == 0 or count >= 255:
            print(f"Input {i+1} sent → Buffer count: {count}")
        if count >= 255:
            if uad.has_overflowed():
                print("Overflow detected correctly!")
            else:
                print("Warning: Buffer full but overflow bit not set!")
            break
    # Clear buffer after test
    uad.write_CSR(uad.read_CSR() | (1 << 17))
    print("\nAfter clearing buffer:")
    print("Buffer count:", uad.buffer_count())
    print("Overflow after clear:", uad.has_overflowed())



# -------------------------------
# Main loop over all instances
# -------------------------------
instances = ["impl0", "impl1", "impl2", "impl3", "impl4", "impl5"]

for impl in instances:
    print(f"\n\n======= Testing {impl} =======\n")
    uad = Uad()
    uad.inst = impl
    
    enable_disable_test(uad)
    bypass_test(uad)
    buffer_halt_test(uad)
    
