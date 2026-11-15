"""No false PDS Moon/Mars target matches from unverified metadata."""
from app.collectors.nasa import _target_confirmed, fetch_planetary_products

MOON="urn:nasa:pds:context:target:satellite.earth.moon"
MARS="urn:nasa:pds:context:target:planet.mars"

def test_target_match_requires_metadata():
    assert _target_confirmed({"ref_lid_target":[MOON]},"moon")
    assert _target_confirmed({"target_name":"Mars"},"mars")
    assert not _target_confirmed({"title":"Cassini image Moon Mars"},"moon")
    assert not _target_confirmed({"ref_lid_target":[MARS]},"moon")
    assert not _target_confirmed({"ref_lid_target":[MOON]},"mars")


def test_pds_returns_only_explicitly_lunar_targeted_products():
    products={
        "data":[
            {"id":"moon-verified","type":"pds:Product_Observational",
             "properties":{"ref_lid_target":[MOON],"pds:Identification_Area.pds:title":["Lunar surface image"]}},
            {"id":"hayabusa-unknown","properties":{"title":"Hayabusa2 mission cruise"}},
            {"id":"mars-verified","properties":{"ref_lid_target":[MARS],"title":"Actual Mars product"}}
        ]
    }
    class Response:
        def raise_for_status(self):pass
        def json(self):return products
    class Client:
        def get(self,url,params,headers):return Response()
    moon=fetch_planetary_products(Client(),"moon",limit=5)
    mars=fetch_planetary_products(Client(),"mars",limit=5)
    assert [row["id"] for row in moon["products"]]==["moon-verified"]
    assert [row["id"] for row in mars["products"]]==["mars-verified"]
    assert moon["target_verification"]=="explicit_target_metadata_required"
    assert moon["analog_results"] is False
