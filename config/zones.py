from core.zones.zone import Zone

ZONES = {

    "cam_1": [
        Zone(
            zone_id="entrance",
            polygon=[(100,100), (500,100), (500,400), (100,400)],
            zone_type="restricted"
        )
    ]
}