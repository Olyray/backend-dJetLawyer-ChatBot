import subprocess

def get_installed_versions():
    result = subprocess.run(['pip', 'freeze'], capture_output=True, text=True)
    return dict(line.split('==') for line in result.stdout.splitlines())

def update_requirements(file_path):
    installed_versions = get_installed_versions()
    
    with open(file_path, 'r') as file:
        requirements = file.readlines()
    
    updated_requirements = []
    for req in requirements:
        package = req.strip().split('==')[0]
        if package in installed_versions:
            updated_requirements.append(f"{package}=={installed_versions[package]}\n")
        else:
            updated_requirements.append(req)
    
    with open(file_path, 'w') as file:
        file.writelines(updated_requirements)

# Usage
update_requirements('requirements.txt')