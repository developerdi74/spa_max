from salon1c import SalonClient, SalonAPIError, make_sign

SALON_ID = "0d190fc8-1c01-11ef-b1bf-f02f7488d897"

client = SalonClient(api_key="110132e6-ba129-4120-ac33-fcd612380121",
                     salon_id=SALON_ID)

# ---- Авторизация через SMS ----
# 1) отправляем код
result = client.auth.auth(SALON_ID, login="79876543210")
# 2) проверяем код и получаем UserToken
data = client.auth.auth(SALON_ID, login="79876543210",
                        confirmation_code="1234")
token = data["UserToken"]
client.usertoken = token

# ---- Авторизация по подписи (sign считается автоматически) ----
data = client.auth.private_auth(
    SALON_ID, phone="79876543210", name="Иван",
    last_name="Иванов", birthday="31.12.1990", sex="1",
)

# ---- Услуги и сотрудники для записи ----
services = client.bookings.book_services(SALON_ID)
staff = client.bookings.book_staff(SALON_ID, service_id=services[0]["id"])

dates = client.bookings.book_dates(SALON_ID,
                                   start_date="20260803T0000",
                                   end_date="20260831T0000")
times = client.bookings.book_times(SALON_ID,
                                   service_id=services[0]["id"],
                                   datetime_="20260805T0900")

# ---- Запись на визит ----
record = client.bookings.book_record(
    SALON_ID,
    record_array=[{
        "datetime": "20260805T0900",
        "service_id": services[0]["id"],
        "staff_id": staff[0]["id"],
    }],
    name="Иван", last_name="Иванов",
)
record_id = record["record_id"]

# ---- Стоимость и оплата ----
cost = client.bookings.record_cost(SALON_ID, record_array=[{
    "datetime": "20260805T0900",
    "service_id": services[0]["id"],
    "staff_id": staff[0]["id"],
}])

client.payments.pay_visit(
    SALON_ID, record_id=record_id, transaction_id="tx-123",
    payment_list=[{"type": "card", "amount": cost["total_amount"]}],
)

# ---- Данные клиента ----
info = client.clients.get_client(SALON_ID)
deposits = client.clients.deposit_list(SALON_ID)
history = client.clients.records_history(SALON_ID)

# ---- Онлайн-магазин ----
price = client.store.price_list(SALON_ID, type="product")
cart = client.store.cart_cost(SALON_ID,
                              cart=[{"purchase_id": price[0]["id"], "count": 1}])

# ---- Терминал самообслуживания (v2) ----
found = client.terminal.find_client_by_phone("79876543210")
term_token = client.terminal.auth("79876543210", name="Иван")["UserToken"]

# ---- Обработка ошибок ----
try:
    client.bookings.cancel_record(SALON_ID, record_id="bad-id")
except SalonAPIError as e:
    print(e.code, e.message)

client.close()