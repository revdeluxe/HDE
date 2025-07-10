from SX127x.LoRa import MODE

modes = {
    name: val
    for name, val in MODE.__dict__.items()
    if name.isupper()
}
print("Available MODEs:", modes)
