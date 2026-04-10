"""
Automated MSI build script for Kinetix
Handles PyInstaller freezing and WiX compilation
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Colors for console output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_step(message):
    """Print step message"""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}[STEP] {message}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(message):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")

def print_error(message):
    """Print error message"""
    print(f"{Colors.RED}✗ {message}{Colors.END}")

def print_warning(message):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")

def run_command(cmd, cwd=None):
    """Run shell command and return success status"""
    try:
        import shlex
        args = shlex.split(cmd, posix=False)
        result = subprocess.run(
            args,
            cwd=cwd,
            shell=False,
            check=True,
            capture_output=True,
            text=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def main():
    """Main build process"""
    
    print(f"\n{Colors.BLUE}{'='*60}")
    print("  Kinetix MSI Build Script")
    print(f"{'='*60}{Colors.END}\n")
    
    # Get paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    dist_dir = project_root / 'dist'
    build_dir = project_root / 'build'
    
    # Step 1: Clean previous builds
    print_step("Cleaning previous builds")
    
    if dist_dir.exists():
        print(f"Removing {dist_dir}")
        shutil.rmtree(dist_dir)
    
    if build_dir.exists():
        print(f"Removing {build_dir}")
        shutil.rmtree(build_dir)
    
    # Clean installer build files
    for pattern in ['*.wixobj', '*.wixpdb']:
        for file in script_dir.glob(pattern):
            file.unlink()
            print(f"Removed {file.name}")
    
    print_success("Build directories cleaned")
    
    # Step 2: Collect static files
    print_step("Collecting Django static files")
    
    success, output = run_command(
        f"{sys.executable} manage.py collectstatic --noinput",
        cwd=project_root
    )
    
    if success:
        print_success("Static files collected")
    else:
        print_error("Failed to collect static files")
        print(output)
        return 1
    
    # Step 3: Run PyInstaller
    print_step("Freezing application with PyInstaller")
    
    spec_file = script_dir / 'command_center.spec'
    
    success, output = run_command(
        f"pyinstaller --clean --noconfirm {spec_file}",
        cwd=script_dir
    )
    
    if success:
        print_success("Application frozen successfully")
    else:
        print_error("PyInstaller failed")
        print(output)
        return 1
    
    # Verify frozen app exists
    frozen_app = dist_dir / 'Kinetix'
    if not frozen_app.exists():
        print_error(f"Frozen application not found at {frozen_app}")
        return 1
    
    print(f"Frozen app size: {get_dir_size(frozen_app):.2f} MB")
    
    # Step 4: Copy additional files
    print_step("Copying additional files")
    
    # Copy config template
    config_template = script_dir / 'config.ini.template'
    if config_template.exists():
        shutil.copy(config_template, frozen_app / 'config.ini.template')
        print_success("Config template copied")
    
    # Copy README
    readme = project_root / 'README.md'
    if readme.exists():
        shutil.copy(readme, frozen_app / 'README.md')
        print_success("README copied")
    
    # Step 5: Test frozen application
    print_step("Testing frozen application")
    
    frozen_exe = frozen_app / 'command_center.exe'
    
    # Test help command
    success, output = run_command(
        f'"{frozen_exe}" --help',
        cwd=frozen_app
    )
    
    if success:
        print_success("Frozen application runs successfully")
    else:
        print_warning("Could not test frozen application")
    
    # Step 6: Check for WiX Toolset
    print_step("Checking WiX Toolset")
    
    wix_installed = False
    for path in os.environ.get('PATH', '').split(os.pathsep):
        candle_exe = Path(path) / 'candle.exe'
        if candle_exe.exists():
            wix_installed = True
            print_success(f"WiX found at {path}")
            break
    
    if not wix_installed:
        print_warning("WiX Toolset not found in PATH")
        print("Download from: https://wixtoolset.org/")
        print("Skipping MSI creation")
        print_success("Frozen application ready at: " + str(frozen_app))
        return 0
    
    # Step 7: Compile WiX
    print_step("Compiling WiX installer")
    
    wxs_file = script_dir / 'product.wxs'
    
    if not wxs_file.exists():
        print_error(f"WiX source file not found: {wxs_file}")
        print("Create product.wxs to build MSI")
        print_success("Frozen application ready at: " + str(frozen_app))
        return 0
    
    # Compile .wxs to .wixobj
    print("Compiling WiX source...")
    success, output = run_command(
        f'candle.exe "{wxs_file}" -ext WixUtilExtension',
        cwd=script_dir
    )
    
    if not success:
        print_error("WiX compilation failed")
        print(output)
        return 1
    
    print_success("WiX source compiled")
    
    # Link .wixobj to .msi
    print("Linking MSI...")
    wixobj_file = script_dir / 'product.wixobj'
    msi_output = dist_dir / 'Kinetix-Setup.msi'
    
    success, output = run_command(
        f'light.exe "{wixobj_file}" -ext WixUtilExtension -out "{msi_output}"',
        cwd=script_dir
    )
    
    if not success:
        print_error("WiX linking failed")
        print(output)
        return 1
    
    print_success("MSI created successfully")
    
    # Step 8: Verify MSI
    if msi_output.exists():
        msi_size = msi_output.stat().st_size / (1024 * 1024)
        print(f"\nMSI size: {msi_size:.2f} MB")
        print(f"MSI location: {msi_output}")
    
    # Final summary
    print(f"\n{Colors.GREEN}{'='*60}")
    print("  Build completed successfully!")
    print(f"{'='*60}{Colors.END}\n")
    
    print(f"Frozen application: {frozen_app}")
    print(f"MSI installer: {msi_output}")
    
    print("\nNext steps:")
    print("1. Test MSI installation on clean Windows VM")
    print("2. Sign MSI with code signing certificate (optional)")
    print("3. Distribute to users")
    
    return 0

def get_dir_size(path):
    """Get directory size in MB"""
    total = 0
    for entry in Path(path).rglob('*'):
        if entry.is_file():
            total += entry.stat().st_size
    return total / (1024 * 1024)

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Build cancelled by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
