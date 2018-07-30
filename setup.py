import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sarc",
    version="1.0.0-1",
    author="leoetlino",
    author_email="leo@leolam.fr",
    description="Nintendo SARC archive reader and writer",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/leoetlino/sarc",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Software Development :: Libraries",
    ],
    python_requires='>=3.6',
    install_requires=['rstb~=1.0', 'PyYAML~=3.12', 'wszst_yaz0~=1.0'],
    entry_points = {
        'console_scripts': [
            'sarc = sarc.__main__:main',
            'sarctool = sarc.__main__:main',
        ]
    },
)
