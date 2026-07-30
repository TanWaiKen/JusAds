from shared.zernio_client import _serialize


class _SdkLikeAccountList:
    def model_dump(self, *, mode, by_alias):
        assert mode == "json"
        assert by_alias is True
        return {
            "accounts": [
                {"_id": "account-123", "platform": "instagram", "username": "brand"}
            ]
        }


def test_zernio_sdk_serialization_preserves_api_aliases_and_platform_strings():
    payload = _serialize(_SdkLikeAccountList())
    assert payload["accounts"][0] == {
        "_id": "account-123",
        "platform": "instagram",
        "username": "brand",
    }
