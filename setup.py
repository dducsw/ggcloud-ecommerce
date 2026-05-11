import setuptools

setuptools.setup(
    name="clickstream-pipeline",
    version="1.0.0",
    packages=setuptools.find_packages(),
    install_requires=[
        "apache-beam[gcp]",
        "google-cloud-bigquery",
        "google-cloud-pubsub",
        "google-cloud-storage",
        "pandas",
        "pyarrow",
    ],
)
