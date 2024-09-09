import sys,os, glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import setuptools, sssekai_streaming_hca_decoder

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()

package_data = []
root_dir = 'sssekai_streaming_hca_decoder'
package_data += glob.glob("vfs/**", recursive=True, root_dir=root_dir)
package_data += glob.glob("emu_cfg/**", recursive=True, root_dir=root_dir)
# keystone
package_data += glob.glob("**/*.dylib", recursive=True, root_dir=root_dir)
package_data += glob.glob("**/*.dll", recursive=True, root_dir=root_dir)
package_data += glob.glob("**/*.so", recursive=True, root_dir=root_dir)
package_data = [fname for fname in package_data if os.path.isfile(os.path.join(root_dir,fname))]
package_data = list(set(package_data))

setuptools.setup(
    name="sssekai_streaming_hca_decoder",
    version=sssekai_streaming_hca_decoder.__version__,
    author="greats3an",
    author_email="greats3an@gmail.com",
    description="Project SEKAI custom streaming CRIWARE HCA Decoder",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mos9527/sssekai_streaming_hca_decoder",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    install_requires=["unicorn==1.0.2","capstone==4.0.1","coloredlogs","numpy","scipy","tqdm"],
    entry_points={"console_scripts": ["sssekai_streaming_hca_decoder = sssekai_streaming_hca_decoder.__main__:__main__"]},
    package_data={'sssekai_streaming_hca_decoder': package_data},
    python_requires=">=3.6",
)
