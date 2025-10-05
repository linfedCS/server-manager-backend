def parse_channels(data_str):
    channels = []

    excluded_params = {"pid", "channel_order", "channel_needed_subscribe_power", "id", "msg"}

    # Убираем лишние символы и разбиваем на каналы
    data_str = data_str.strip()
    if not data_str:
        return channels

    # Разбиваем по каналам (символ |)
    for channel_str in data_str.split('|'):
        channel = {}

        # Разбиваем параметры канала
        for param in channel_str.split():
            if '=' in param:
                key, value = param.split('=', 1)

                if key in excluded_params:
                    continue

                # Очищаем значение от кавычек
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]

                # Пытаемся преобразовать в int, если не получается - оставляем строкой
                try:
                    channel[key] = int(value)
                except ValueError:
                    channel[key] = value

        if channel:  # Добавляем только непустые каналы
            channels.append(channel)

    return channels

def parse_clients(data_str):
    clients = []
    excluded_params = {"clid", "client_database_id", "id", "msg"}

    data_str = data_str.strip()
    if not data_str:
        return clients

    for client_str in data_str.split('|'):
        client = {}

        for param in client_str.split():
            if '=' in param:
                key, value = param.split('=', 1)

                if key in excluded_params:
                    continue

                if key == 'client_nickname':
                    value = value.replace('\\s', ' ')

                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]

                try:
                    client[key] = int(value)
                except ValueError:
                    client[key] = value

        if client:
            clients.append(client)

    return clients
