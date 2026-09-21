import pytest

from data.generator import generate_dataset

# Small n for test speed; the shape/behavior we assert on doesn't depend on scale.
_TEST_N_CUSTOMERS = 400
_TEST_N_PRODUCTS = 20


@pytest.fixture(scope="session")
def dataset():
    return generate_dataset(n_customers=_TEST_N_CUSTOMERS, n_products=_TEST_N_PRODUCTS)
