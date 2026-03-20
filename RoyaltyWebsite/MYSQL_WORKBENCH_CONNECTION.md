# Connect to the database from MySQL Workbench

The app uses **MySQL**. Connection details come from your environment (`.env` or `coin.env` in the **django-docker-compose** folder).

## Where to get the values

| Parameter   | Where it comes from | Example (your env may differ) |
|------------|----------------------|-------------------------------|
| **Host**   | `EC2_DB_HOST` or `LOCAL_DB_HOST` | e.g. `ec2-54-84-50-236.compute-1.amazonaws.com` (EC2) or `127.0.0.1` (local) |
| **Port**   | Always **3306**      | 3306 |
| **User**   | `EC2_DB_USER` or `LOCAL_DB_USER` | e.g. `admincoin` |
| **Password** | `EC2_DB_PASSWORD` or `LOCAL_DB_PASSWORD` | (from your .env – never commit this) |
| **Default schema** | Main app DB is **db4** | `db4` (there is also `db2`) |

- For **production/EC2**: use `EC2_DB_*` from the server’s `.env` or your local `.env` if you point at the same DB.
- For **local MySQL**: use `LOCAL_DB_*`.

## MySQL Workbench steps

1. **MySQL Workbench** → **Database** → **Manage Connections** (or **+** to add a connection).
2. Set:
   - **Connection Name:** e.g. `Coin Digital – db4`
   - **Hostname:** value of `EC2_DB_HOST` or `LOCAL_DB_HOST` (see above)
   - **Port:** `3306`
   - **Username:** value of `EC2_DB_USER` or `LOCAL_DB_USER`
   - **Password:** click **Store in Keychain…** (or **Store in Vault…**) and enter the value of `EC2_DB_PASSWORD` or `LOCAL_DB_PASSWORD`
   - **Default Schema:** `db4` (optional; you can select it after connecting)
3. **Test Connection** → **OK** → **Close**.

To see the actual Host/User/Password on your machine (without printing the password in logs), you can run from the project root:

```bash
cd django-docker-compose
grep -E "^EC2_DB_HOST=|^EC2_DB_USER=" .env coin.env 2>/dev/null | head -5
```

Do **not** put the password in a script or commit it; use MySQL Workbench’s store-password option.

## Database address (summary)

- **Host:** `EC2_DB_HOST` or `LOCAL_DB_HOST` from `.env` / `coin.env`  
  Example: `ec2-54-84-50-236.compute-1.amazonaws.com`
- **Port:** `3306`
- **Database (schema):** `db4` (main), or `db2` if you use the second DB

So the “database address” is: **`<host>:3306`** (e.g. `ec2-54-84-50-236.compute-1.amazonaws.com:3306`) with username and password from the same env file.
