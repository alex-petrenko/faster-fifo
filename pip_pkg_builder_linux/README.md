### Instructions on how to convert ```linux_x86_64.whl``` to ```manylinux2014.whl``` for the Pypi (pip) repository

These steps are specific to creating a ```manylinux2014``` wheel. For the ```manylinux2010``` and ```manylinux1``` formats,
the steps might remain similar.
1. Download the ```manylinux2014``` docker with the command  
```docker pull quay.io/pypa/manylinux2014_x86_64```  
2. Run the docker file with the following command:  
```docker run --name manylinux_d -i -t quay.io/pypa/manylinux2014_x86_64:latest /bin/bash```  
This opens up a shell within the docker container in the terminal in which this command was executed.
3. In another terminal copy the contents of your project to a folder called ```src```
in the docker by using:  
```docker cp path-to-package/. manylinux_d:/src/``` 
4. The ```/opt/python/``` folder has various versions of python installed to build your wheels with.
For example ```cp37-cp37m``` comes with Python 3.7. The folders for other python versions are named with a similar format
and the docker image comes pre-installed with 3.5, 3.6, 3.7 and 3.8.  
5. Now we are gonna assume that we are building a wheel using Python 3.7.
6. Run the following command to build the ```linux_x86_64``` wheel  which is written to the ```output``` folder:  
```/opt/python/cp37-cp37m/bin/pip wheel /src -w /output```  
7. The ```linux_x86_64``` wheel can now be converted into a ```manylinux2014``` wheel with the following command and writes it to the same ```output``` folder:  
```auditwheel repair /src/package_name-version-cp37-cp37m-linux_x86_64.whl -w /output```  
8. Next copy this manylinux wheel from the docker to any folder perhaps say ```manylinux_wheel``` with the following command:  
```docker cp manylinux_d:/output/package_name-version-cp37-cp37m-manylinux2014_x86_64.whl path-to-package/manylinux_wheel/```
9. Also copy the ```package_name.tar.gz``` file from ```dist``` folder into the ```manylinux_wheel``` folder. This can be created by running the following command:  
```python3 setup.py sdist``` 
10. Now run the following command to upload it to the pypi repository:
``` python3 -m twine upload manylinux_wheel/*```