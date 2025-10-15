# from config.database import create_connection, DB_CONFIG
# import datetime

# def save_email_db(to_from:str,to_email: str, subject: str, body: str):
#     try:
#         conn = create_connection(DB_CONFIG)
#         if not conn:
#             raise Exception("Failed to connect to DB")
#         cursor = conn.cursor()

#         sql = """
#         INSERT INTO emails (to_from,to_email, subject, body, created_at)
#         VALUES (%s,%s, %s, %s, %s)
#         """

#         cursor.execute(sql, (
#             to_from,
#             to_email,
#             subject,
#             body,
#             datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
#         ))

#         conn.commit()
#         print("✅ Email saved to DB:", to_email)
#         return {"status": "success", "message": "Email saved in DB"}
#     except Exception as e:
#         print("❌ Error saving email to DB:", e)
#         return {"status": "error", "message": str(e)}
#     finally:
#         if conn:
#             conn.close()
