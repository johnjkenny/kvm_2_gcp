from setuptools import setup


try:
    setup(
        name='kvm_2_gcp',
        version='1.0.0',
        entry_points={'console_scripts': [
            'k2g = kvm_2_gcp.cli:k2g_parent',
            'k2g-init = kvm_2_gcp.cli:init',
            'k2g-deploy = kvm_2_gcp.cli:deploy',
            'k2g-controller = kvm_2_gcp.cli:controller',
            'k2g-images = kvm_2_gcp.cli:images',
            'k2g-remote-images = kvm_2_gcp.cli:remote_images',
            'k2g-remote-deploy = kvm_2_gcp.cli:remote_deploy',
            'k2g-remote-rocky-images = kvm_2_gcp.cli:rocky_remote_images',
            'k2g-remote-ubuntu-images = kvm_2_gcp.cli:ubuntu_remote_images',
            'k2g-remote-gcp-images = kvm_2_gcp.cli:gcp_remote_images',
        ]},
    )
    exit(0)
except Exception as error:
    print(f'Failed to setup package: {error}')
    exit(1)
