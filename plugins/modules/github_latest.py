DOCUMENTATION = r'''
---
module: github_latest

short_description: This module retrieves the latest release from a github repo

description: This module retrieves the latest release from a github repo

version_added: "0.0.1"

options:
    repo:
        required: true
        type: str
        description: The GitHub repository to retrieve the latest release from
    token:
        required: false
        type: str
        description: A GitHub token (e.g. PAT)

author:
    - delfino (@x_delfino)
'''

EXAMPLES = r"""
- name: Get latest release of owner/repo
  x_delfino.common.github_latest:
    repo: owner/repo
"""

RETURN = r'''
latest_version:
    description: The latest GitHub release for the repository.
    returned: success
    type: str
    sample: v1.0.0
'''

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible.module_utils.urls import Request  # noqa: E402
import os  # noqa: E402
import json  # noqa: E402
from urllib.error import HTTPError  # noqa: E402


def get_latest_release(repo, token=None):
    """Get the latest release version of a GitHub repository."""
    url = f'https://api.github.com/repos/{repo}/releases/latest'
    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'
    try:
        r = Request(headers)
        with r.open('GET', url) as response:
            data = json.load(response)
            return data['tag_name'].strip()
    except HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Repository '{repo}' releases not found.")
        else:
            raise ValueError(f"Failed to fetch data from GitHub API: {e}")
    except Exception as e:
        raise ValueError(f"An error occurred: {e}")


def main():
    module = AnsibleModule(
        argument_spec=dict(
            repo=dict(type='str', required=True),
            token=dict(type='str', required=False, no_log=True)
        ),
        supports_check_mode=True
    )

    repo = module.params['repo']
    token = module.params['token']
    if not token:
        token = os.getenv('GITHUB_TOKEN', None)

    try:
        latest_version = get_latest_release(repo, token)
        module.exit_json(
            changed=False,
            latest_version=latest_version
        )

    except ValueError as e:
        module.fail_json(msg=str(e))


if __name__ == '__main__':
    main()
