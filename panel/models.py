from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models

class UserManager(DjangoUserManager): 
    """Cuida al modelo si alguien intenta editar su rol mediante create_user() esto
    revienta en vez de aceptarlo.
    Vamos a modificar el método de django para meterle una validación y así evitar que un atacante
    escale privilegios desde el frontend mediante las vistas que utilizan create_user()"""

    def create_user(self, username, email=None, password=None, **extra_fields):
        if 'rol' in extra_fields:
            raise ValueError("No se acepta el parametro 'rol'.")
        extra_fields.setdefault('rol', User.Rol.CLIENTE)
        return super().create_user(username, email, password, **extra_fields)

class User(AbstractUser): #
    class Rol(models.TextChoices): #Subclase de enumeracion, permite hacer cosas como: User.objects.create(rol=User.Rol.MESERO)
        CLIENTE = 'cliente', 'Cliente' #Aquí van todos los roles que queremos, primero el sufijo de base de datos y luego la etiqueta 
        MESERO = 'mesero', 'Mesero' #BD, Etiqueta
        ADMIN = 'admin', 'Admin'

    telefono = models.CharField(max_length=20, blank=True)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.CLIENTE)
    objects = UserManager()

    @classmethod
    def crear_mesero(cls, username, email=None, password=None, **extra_fields):
        """Crea explicitamente un mesero. Crea un usuario, define su nuevo rol y luego lo actualiza"""
        usuario = cls.objects.create_user(username, email, password, **extra_fields)
        usuario.rol = cls.Rol.MESERO
        usuario.save(update_fields=['rol'])
        return usuario

    @classmethod
    def crear_admin(cls, username, email=None, password=None, **extra_fields):
        """Crea explicitamente un administrador por la via controlada.

        Espejo de crear_mesero: create_user() no acepta 'rol', asi que el
        rol se asigna despues del create. Un admin nunca nace desde el
        frontend, solo desde aqui o desde un management command.
        """
        usuario = cls.objects.create_user(username, email, password, **extra_fields)
        usuario.rol = cls.Rol.ADMIN
        usuario.save(update_fields=['rol'])
        return usuario

    def reservas_pendientes(self):
        """Reservas confirmadas que aun no han terminado."""
        from booking.models import Reserva  # import local: evita el ciclo panel <-> booking

        return Reserva.pendientes().filter(cliente=self)

    def desactivar(self):
        """Desactiva la cuenta y cierra sus compromisos.

        Cancela las reservas pendientes (cerrando la cuenta abierta si la
        hay): un cliente inactivo no puede entrar a cancelarlas el mismo, y
        sus reservas seguirian bloqueando mesas.

        Devuelve cuantas reservas cancelo.
        """
        canceladas = 0
        for reserva in self.reservas_pendientes():
            reserva.cancelar(cerrar_cuenta=True)
            canceladas += 1

        self.is_active = False
        self.save(update_fields=['is_active'])
        return canceladas

    def activar(self):
        """Reactivar la cuenta."""
        self.is_active = True
        self.save(update_fields=['is_active'])

    def __str__(self):
        return self.email or self.username

