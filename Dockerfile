FROM python:3.7

RUN pip install kubernetes ipdb dask distributed jupyterlab

COPY dask-operator /dask-operator

CMD python /dask-operator/operator.py
