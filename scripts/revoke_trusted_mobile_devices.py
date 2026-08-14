from app.services.trusted_mobile_device_service import (
    revoke_all_trusted_devices,
)


def main() -> None:
    count = (
        revoke_all_trusted_devices()
    )

    print(
        f"Revoked {count} trusted mobile device(s)."
    )


if __name__ == "__main__":
    main()
