from setuptools import setup


try:
    setup(
        name='kvm_2_gcp',
        version='1.0.0',
        entry_points={'console_scripts': [
            'k2g = kvm_2_gcp.cli:k2g_parent',
        ]},
    )
    exit(0)
except Exception as error:
    print(f'Failed to setup package: {error}')
    exit(1)
