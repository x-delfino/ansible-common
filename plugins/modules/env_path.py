DOCUMENTATION = r'''
---
module: env_path

short_description: This module adds paths to PATH

description: This module adds paths to PATH

version_added: "0.0.1"

options:
    path:
        required: true
        type: str
        description: The path to add
    shell:
        required: false
        type: str
        description: The type of shell in use
        choices:
          - zsh
          - fish
          - bash
          - sh
    state:
        required: false
        type: str
        description: The desired state of the entry
        default: present
        choices:
          - present
          - absent
    target:
        required: false
        type: str
        description: Whether to target rc or profile files
        default: profile
        choices:
          - profile
          - rc
    home:
        required: false
        type: path
        description: Override the home directory
    xdg_config_home:
        required: false
        type: path
        description: Override the XDG_CONFIG_HOME directory
    zdotdir:
        required: false
        type: path
        description: Override the ZDOTDIR directory

author:
    - delfino (@x_delfino)
'''

EXAMPLES = r"""
- name: Add `~/.local/bin` to path
  x_delfino.common.env_path:
    path: ~/.local/bin
"""

RETURN = r'''
updated_files:
    description: A list of the files that have been updated
    returned: changed
    type: list
    elements: str
    sample:
      - /home/ansible/.profile
shell:
    description: The shell that was selected/detected
    returned: changed
    type: str
    sample: zsh
target:
    description: The target (profile/rc)
    returned: changed
    type: str
    sample: zsh
'''


import os  # noqa: E402
import re  # noqa: E402
from ansible.module_utils.basic import AnsibleModule  # noqa: E402


def get_shell_for_home(home):
    try:
        with open("/etc/passwd", "r") as passwd:
            for line in passwd:
                parts = line.strip().split(":")
                if len(parts) >= 7 and parts[5] == home:
                    return os.path.basename(parts[6])
    except Exception:
        pass
    return "sh"


def remove_line(content, path, shell):
    escaped = re.escape(path)
    if shell == "fish":
        pattern = (
            rf'(?ms)^if\s+test\s+-d\s+{escaped}\s*\n'
            rf'\s*set\s+-gx\s+PATH\s+{escaped}\s+\$PATH\s*\nend\s*'
        )
        return re.sub(pattern, '', content).strip() + "\n"
    elif shell == "zsh":
        pattern = (
            rf'\[\[\s+-d\s+"?{escaped}"?\s*\]\]\s*&&\s*'
            rf'path\+=\("?\s*{escaped}\s*"?\)'
        )
        return re.sub(pattern, '', content).strip() + "\n"
    else:
        pattern = (
            rf'\[\s+-d\s+"?{escaped}"?\s*\]\s*&&\s*'
            rf'export\s+PATH="?\s*{escaped}:?\$PATH"?'
        )
        return re.sub(pattern, '', content).strip() + "\n"


def get_rc_files(shell, home, env, zdotdir=None, xdg_config_home=None):
    zdotdir = zdotdir or env.get("ZDOTDIR") or home
    xdg_config_home = xdg_config_home or env.get("XDG_CONFIG_HOME")
    xdg_config_home = xdg_config_home or os.path.join(home, ".config")
    return {
        'bash': {
            'profile': [os.path.join(home, ".bash_profile")],
            'rc': [os.path.join(home, ".bashrc")]
        },
        'zsh': {
            'profile': [os.path.join(zdotdir, ".zprofile")],
            'rc': [os.path.join(zdotdir, ".zshrc")]
        },
        'fish': {
            'profile': [os.path.join(xdg_config_home, "fish", "config.fish")],
            'rc': [os.path.join(xdg_config_home, "fish", "config.fish")]
        },
        'sh': {
            'profile': [os.path.join(home, ".profile")],
            'rc': []
        }
    }.get(shell, {
        'profile': [os.path.join(home, ".profile")],
        'rc': []
    })


def get_path_line(shell, path):
    if shell == "fish":
        return f"if test -d {path}\n  set -gx PATH {path} $PATH\nend"
    elif shell == "zsh":
        return f'[[ -d "{path}" ]] && path+=("{path}")'
    else:
        return f'[ -d "{path}" ] && export PATH="{path}:$PATH"'


def line_exists(content, path, shell):
    escaped = re.escape(path)
    if shell == "fish":
        return re.search(rf"set\s+-gx\s+PATH\s+{escaped}(\s|$)", content)
    elif shell == "zsh":
        return re.search(rf"path\+\=\(\s*{escaped}\s*\)", content)
    else:
        return re.search(rf'export\s+PATH="?{escaped}:?\$PATH"?', content)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type="str", required=True),
            target=dict(type="str",
                        choices=["profile", "rc"],
                        default="profile"),
            state=dict(type="str",
                       choices=["present", "absent"],
                       default="present"),
            shell=dict(type="str",
                       choices=["zsh", "fish", "bash", "sh"]),
            home=dict(type="path"),
            zdotdir=dict(type="path"),
            xdg_config_home=dict(type="path"),
        ),
        supports_check_mode=True
    )

    path = module.params["path"]
    target = module.params["target"]
    state = module.params["state"]
    shell = module.params["shell"]
    home = module.params["home"]
    env = os.environ

    if not shell:
        if not home:
            shell = os.path.basename(env.get("SHELL", "/bin/sh"))
        else:
            shell = get_shell_for_home(home)
    shell = shell.lower().strip()

    if not home:
        home = env.get("HOME")
    else:
        env = {}

    shell_files = get_rc_files(
        shell,
        home,
        env,
        zdotdir=module.params.get("zdotdir"),
        xdg_config_home=module.params.get("xdg_config_home")
    )

    files_to_edit = shell_files.get(target, [])

    if not files_to_edit:
        module.exit_json(changed=False, msg=(
            f"No suitable config file for shell"
            f"'{shell}' and target '{target}'"
        ))

    line = get_path_line(shell, path)
    changed = False
    updated_files = []

    for file_path in files_to_edit:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        if not os.path.exists(file_path):
            if state == "present":
                with open(file_path, "w") as f:
                    f.write(line + "\n")
                changed = True
                updated_files.append(file_path)
            continue

        with open(file_path, "r+") as f:
            content = f.read()
            needs_add = (
                state == "present"
                and not line_exists(content, path, shell)
            )
            needs_remove = (
                state == "absent"
                and line_exists(content, path, shell)
            )
            if module.check_mode:
                module.exit_json(
                    changed=needs_add or needs_remove,
                    updated_files=[],
                    shell=shell,
                    target=target
                )
            if needs_add:
                f.seek(0, os.SEEK_END)
                if content and not content.endswith('\n'):
                    f.write("\n")
                f.write(line + "\n")
                changed = True
                updated_files.append(file_path)
            elif needs_remove:
                new_content = remove_line(content, path, shell)
                with open(file_path, "w") as f_write:
                    f_write.write(new_content.rstrip() + "\n")
                changed = True
                updated_files.append(file_path)

    module.exit_json(
        changed=changed,
        updated_files=updated_files,
        shell=shell,
        target=target
    )


if __name__ == "__main__":
    main()
