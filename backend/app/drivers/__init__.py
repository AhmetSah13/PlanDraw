"""
Donanım sürücüleri: resmi komut sınırı ``List[Command]`` (``app.execution.commands``).

Paket kökü tüm sürücüleri önceden yüklemez; döngüsel import riski azalır.
İhtiyaç duyulan modülü doğrudan içe aktarın::

    from app.drivers.base import RobotDriver
    from app.drivers.file_driver import FileDriver
    from app.drivers.serial_driver import SerialDriver
"""
