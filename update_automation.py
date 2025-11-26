#!/usr/bin/env python3
import os
import subprocess
import shutil
from datetime import datetime
import argparse
import zipfile

# ------------------- Git Functions -------------------
def get_staged_files():
    """Return a list of staged files and print them."""
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', '--cached'],
            capture_output=True, text=True, check=True
        )
        files = result.stdout.strip().splitlines()
        if files:
            print("Detected staged files:")
            for f in files:
                print(f)
        else:
            print("No staged files detected.")
        return [f for f in files if f]
    except subprocess.CalledProcessError:
        print("Error: This directory is not a Git repository or Git is not installed.")
        return []

# ------------------- Path Utilities -------------------
def path_to_folder_name(file_path):
    """Convert a file path to a single-level folder name by replacing all slashes with '_'."""
    dir_path = os.path.dirname(file_path)
    folder_name = dir_path.replace('/', '_').replace('\\', '_')
    return folder_name

# ------------------- Update Folder -------------------
def create_update_folder(project_name='', default_root='updates', conf_path='update.conf'):
    """
    Creates a folder like updates/update-<project>-YYYY-MM-DD or updates/update-YYYY-MM-DD
    Handles duplicates by appending v2, v3, etc.
    Returns the full path to the update folder.
    """
    base_path = os.getcwd()
    update_path = os.path.join(base_path, default_root)

    # Check for update.conf
    if os.path.exists(conf_path):
        with open(conf_path, 'r') as f:
            for line in f:
                if line.strip().startswith('update_path'):
                    path_str = line.split('=', 1)[1].strip().strip('\'"')
                    update_path = path_str
                    break

    today_str = datetime.today().strftime('%d-%m-%Y')
    if project_name:
        folder_name = f"update-{project_name}-{today_str}"
    else:
        folder_name = f"update-{today_str}"

    full_path = os.path.join(update_path, folder_name)

    # Handle duplicates
    counter = 2
    unique_path = full_path
    while os.path.exists(unique_path):
        unique_path = f"{full_path}-v{counter}"
        counter += 1

    os.makedirs(unique_path)
    return unique_path

# ------------------- Copy Files -------------------
def copy_files_to_update(staged_files, update_folder):
    """Copy each staged file into a folder inside update_folder."""
    for file_path in staged_files:
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} does not exist. Skipping.")
            continue

        folder_name = path_to_folder_name(file_path)
        dest_folder = os.path.join(update_folder, folder_name)
        os.makedirs(dest_folder, exist_ok=True)

        file_name = os.path.basename(file_path)
        dest_file_path = os.path.join(dest_folder, file_name)
        shutil.copy2(file_path, dest_file_path)
        print(f"Copied {file_path} → {dest_file_path}")

# ------------------- Zip Update Folder -------------------
def zip_update_folder(update_folder):
    """
    Zips the entire update_folder into a zip file with the folder itself as top-level.
    Handles duplicates by adding v2, v3, etc.
    Returns the path to the created zip file.
    """
    parent_dir = os.path.dirname(update_folder)
    base_name = os.path.basename(update_folder)
    zip_path = os.path.join(parent_dir, f"{base_name}.zip")

    # Handle duplicate zip files
    counter = 2
    unique_zip_path = zip_path
    while os.path.exists(unique_zip_path):
        unique_zip_path = os.path.join(parent_dir, f"{base_name}-v{counter}.zip")
        counter += 1

    # Create zip
    with zipfile.ZipFile(unique_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(update_folder):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, parent_dir)
                zipf.write(file_path, arcname)
    print(f"Update folder zipped to: {unique_zip_path}")
    return unique_zip_path

# ------------------- CLI -------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="""
Prepare an update package from staged Git files.

This script requires Git. It detects staged files,
copies them into a structured update folder, and prepares them for deployment.

By default, the update folder is: project_root/updates/update-YYYY-MM-DD
You can override this by creating 'update.conf' in the script directory with:
update_path='C://Your/Path'
"""
    )
    parser.add_argument(
        '-p', '--project', type=str, default=None,
        help='Optional project name to include in folder and zip (e.g., AVMIS)'
    )
    parser.add_argument(
        '-v', '--version', action='version', version='Update Preparer 1.3'
    )
    return parser.parse_args()

# ------------------- Main -------------------
if __name__ == "__main__":
    args = parse_args()

    # Ask for project name if not provided
    if args.project is None:
        project_input = input("Enter project name (or press Enter to skip): ").strip()
        project_name = project_input if project_input else ''
    else:
        project_name = args.project.strip()

    staged_files = get_staged_files()
    if staged_files:
        update_folder = create_update_folder(project_name=project_name)
        copy_files_to_update(staged_files, update_folder)
        print(f"\nUpdate prepared in: {update_folder}")
        zip_update_folder(update_folder)
