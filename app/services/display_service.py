def display_name(name: str) -> str:
    """
    Converts:

    meint​e_hibma

    into

    Meinte Hibma
    """

    if not name:
        return ""

    return (
        name.replace("_", " ")
            .title()
    )