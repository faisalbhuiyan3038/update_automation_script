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

def get_files_between_commits(commit1, commit2):
    """Return a list of files changed between two commits and print them."""
    print(f"Preparing update for changes from {commit1} → {commit2}")
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', commit1, commit2],
            capture_output=True, text=True, check=True
        )
        files = [f for f in result.stdout.strip().splitlines() if f]
        if files:
            print(f"Detected {len(files)} files changed between {commit1} and {commit2}:")
            for f in files:
                print(f)
        else:
            print(f"No files changed between {commit1} and {commit2}.")
        return files
    except subprocess.CalledProcessError:
        print("Error: invalid commits or not a Git repository.")
        return []

# ------------------- SQL File Handling -------------------
def get_sql_changes(file_path, commit1=None, commit2=None):
    """
    Extract only the actual changed content from SQL files.
    Returns the changed lines without git diff markers.
    """
    try:
        if commit1 and commit2:
            # Get diff between two commits with only added lines
            result = subprocess.run(
                ['git', 'diff', commit1, commit2, '--', file_path],
                capture_output=True, text=True, check=True
            )
        else:
            # Get diff for staged changes with only added lines
            result = subprocess.run(
                ['git', 'diff', '--cached', '--', file_path],
                capture_output=True, text=True, check=True
            )
        
        diff_content = result.stdout
        return extract_changed_lines(diff_content)
    except subprocess.CalledProcessError as e:
        print(f"Warning: Could not generate diff for {file_path}: {e}")
        return None

def extract_changed_lines(diff_content):
    """
    Extract only the changed lines (added lines) from git diff output.
    Filters out git diff headers and context lines, preserving actual content.
    """
    if not diff_content or not diff_content.strip():
        return None
    
    lines = diff_content.split('\n')
    changed_lines = []
    
    for line in lines:
        # Skip diff headers and metadata
        if line.startswith('diff --git') or line.startswith('index ') or \
           line.startswith('--- ') or line.startswith('+++ ') or \
           line.startswith('@@'):
            continue
        
        # Extract added lines (lines starting with + but not ++)
        if line.startswith('+') and not line.startswith('+++'):
            # Remove the + prefix
            content_line = line[1:]
            changed_lines.append(content_line)
    
    # Join lines and strip leading/trailing whitespace from the entire content
    result = '\n'.join(changed_lines)
    # Remove leading empty lines and standalone semicolons at the start
    result = result.lstrip('\n ;')
    
    return result if result.strip() else None

def save_sql_changes(file_path, changed_content, dest_file_path):
    """
    Save only the changed SQL content to the destination file.
    """
    if not changed_content or not changed_content.strip():
        print(f"Warning: No changes found for {file_path}")
        return False
    
    # Create a header comment
    header = f"""--
-- SQL CHANGES: {file_path}
-- This file contains only the changed content for this SQL file
-- Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- 

"""
    
    with open(dest_file_path, 'w', encoding='utf-8') as f:
        f.write(header)
        f.write(changed_content)
    
    return True

# ------------------- Path Utilities -------------------
def path_to_folder_name(file_path):
    """Convert a file path to a single-level folder name by replacing all slashes with '_'."""
    dir_path = os.path.dirname(file_path)
    folder_name = dir_path.replace('/', '_').replace('\\', '_')
    return folder_name

def is_sql_file(file_path):
    """Check if the file is a SQL file based on extension."""
    return file_path.lower().endswith('.sql')

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
def copy_files_to_update(files, update_folder, commit1=None, commit2=None):
    """Copy each file into a folder inside update_folder."""
    for file_path in files:
        if not os.path.exists(file_path):
            print(f"Warning: {file_path} does not exist. Skipping.")
            continue

        folder_name = path_to_folder_name(file_path)
        dest_folder = os.path.join(update_folder, folder_name)
        os.makedirs(dest_folder, exist_ok=True)

        file_name = os.path.basename(file_path)
        dest_file_path = os.path.join(dest_folder, file_name)
        
        if is_sql_file(file_path):
            # Handle SQL files specially - extract only changed content
            print(f"Extracting changed content for {file_path}...")
            changed_content = get_sql_changes(file_path, commit1, commit2)
            if changed_content:
                if save_sql_changes(file_path, changed_content, dest_file_path):
                    print(f"Created SQL changes file: {dest_file_path}")
                else:
                    print(f"Warning: Failed to save SQL changes for {file_path}")
            else:
                print(f"Warning: No changes found for SQL file {file_path}, skipping.")
        else:
            # Handle non-SQL files normally
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
Prepare an update package from staged Git files or between two commits.

This script requires Git. It detects staged files or files between commits,
copies them into a structured update folder, and prepares them for deployment.

By default, the update folder is: project_root/updates/update-YYYY-MM-DD
You can override this by creating 'update.conf' in the script directory with:
update_path='C://Your/Path'

IMPORTANT: For SQL files, this script extracts only the changed content
instead of copying the entire file. The SQL files will contain only the
new or modified lines, making them suitable for incremental updates.
"""
    )
    parser.add_argument(
        '-p', '--project', type=str, default=None,
        help='Optional project name to include in folder and zip (e.g., AVMIS)'
    )
    parser.add_argument(
        '-c', '--commits', nargs=2, metavar=('COMMIT1', 'COMMIT2'),
        help='Optional: provide two commit hashes to prepare update of all changed files between them'
    )
    parser.add_argument(
        '-v', '--version', action='version', version='Update Preparer 1.8 (SQL Changes Support)'
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

    # Decide which files to prepare
    if args.commits:
        commit1, commit2 = args.commits
        files_to_prepare = get_files_between_commits(commit1, commit2)
    else:
        commit1 = None
        commit2 = None
        files_to_prepare = get_staged_files()

    if files_to_prepare:
        update_folder = create_update_folder(project_name=project_name)
        copy_files_to_update(files_to_prepare, update_folder, commit1, commit2)
        print(f"\nUpdate prepared in: {update_folder}")
        zip_update_folder(update_folder)