### Instructions on how to convert linux_x86_64.whl to manylinux.whl for the pypi (pip) repository

1. Initially run the following command to generate the distribution archives  
```python3 setup.py sdist bdist_wheel```  
This creates a ```dist``` folder with a ```package_name_linux_x86_64.whl``` file and
a ```package_name.tar.gz```
2. Download the ```manylinux2014``` docker with the command  
```docker pull quay.io/pypa/manylinux2014_x86_64```  
3. Run the docker file with the following command:  
```docker run --name manylinux_d -i -t quay.io/pypa/manylinux2014_x86_64:latest /bin/bash```  
This opens up a shell within the docker container in the terminal in which this command was executed.
4. In another terminal copy the ```package_name_linux_x86_64.whl``` file from the ```dist``` folder to a new folder called ```src```
in the docker by using:  
```docker cp path-to-package/dist/package_name_linux_x86_64.whl manylinux_d:/src/```
5. Now run the following command in the docker terminal:  
```auditwheel repair /src/package_name_linux_x86_64.whl -w /output```  
This would have created a ```manylinux2014``` wheel in the ```output``` folder.
6. Next copy this out from the docker to any folder perhaps say ```manylinux_wheel``` with the following command:  
```docker cp manylinux_d:/output/package_name-manylinux2014_x86_64.whl path-to-package/manylinux_wheel/```
7. Also copy the ```package_name.tar.gz``` file from ```dist``` folder into the ```manylinux_wheel``` folder.
8. Now run the following command to upload it to the pypi repository:
``` python3 -m twine upload manylinux_wheel/*```