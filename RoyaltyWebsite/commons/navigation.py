navigation = {
    "admin": {
        "Home": "home",
        "Upload Data": "upload",
        "Manage Users": "groups",
        "Insert User":  "insert_user",
        "Payments": "payments",
        "Insert User": "person_add",
        "Balance Reports": "summarize",
        "Releases": "library_music",
        "Change Password": "password"
    },
    "intermediate":  {
        "Home": "home",
        "Manage Users": "groups",
        "Payments": "payments",
        "Releases": "library_music",
        "Insert User": "person_add",
        "Change Password": "password",
    },
    'normal':  {
        "Royalty Stats": "query_stats",
        "Payments": "payments",
        "Download Royalties": "download",
        "Releases": "library_music",
        "Change Password": "password"
    },
    'split_recipient': {
        "Dashboard": "bar_chart_4_bars",
        "Royalties": "dashboard",
        "Analytics": "analytics",
        "Payments": "payments",
        "Requests": "help",
        "Change Password": "password"
    }
}

def get_navigation(page, navigation):
    output = []
    for name, icon in navigation.items():
        nav_item = "nav-item"
        extension = name.lower().replace(" ", "_")
        if name == page or extension == page:
            nav_item += " active"
        output.append((name, extension, nav_item, icon))
    return output
