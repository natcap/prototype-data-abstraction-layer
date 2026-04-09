# Data Hub Abstraction Layer API

An API, built with FastAPI, for querying the Natural Capital Alliance Data Hub from InVEST. The goal is to allow InVEST to query the Data Hub for relevant model inputs, directly from the Workbench.

This API takes parameters from InVEST and uses them to construct a query that CKAN / Solr will recognize. It then processes the CKAN query results and returns them in a format better suited for ingestion into InVEST.

## Installation

Required dependencies are listed in `requirements.txt`. If you want to run tests, you will also need to install the dependencies in `requirements-dev.txt`.

## Running the Development API

From within `/fastapi-demo/src/dhal_api/`, run `fastapi dev`. By default, FastAPI uses port `:8000`. The automated docs (which include an interface for testing endpoints) will be available at http://127.0.0.1:8000/docs

### Developing against different versions of the Data Hub

While this API is in early development, `main.py` includes the CKAN URL and relevant Vocabulary IDs for the Prodution and Staging Data Hub sites, as well as for my (Megan's) local CKAN cluster. Simply uncomment the constants relevant to the site you want to test against. (Note: we recently put the Staging Hub behind a password due to increased bot activity; the API isn't currently set up to handle this, so I recommend using the Production Hub or a local cluster for now.)

Developing against a local CKAN cluster will require updating the `PLACE_VOCAB_ID` and `COLLECTION_VOCAB_ID` to reflect the IDs of those Tag Vocabularies in your CKAN instance. You will also need to uncomment the line in `search_dataset` that sets `session.verify=False`. This is because the development version of CKAN uses a self-signed certificate, resulting in an `SSLCertVerificationError`.
