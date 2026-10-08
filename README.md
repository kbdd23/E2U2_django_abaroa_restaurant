# Restaurante Abaroa - Backend 
Segunda etapa del proyecto académico iniciado en la Unidad 1.

Esta etapa incorpora persistencia real en base de datos: landing, reserva de mesas, atención de mesas por parte de los meseros y panel de administración para gestionar los objetos de la carta, usuarios y mesas.

# Base de datos
El proyecto usa MongoDB Atlas en la nube mediante `django-mongodb-backend` en lugar de MySQL por defecto de Django.

La conexión se configura en un archivo `db.env` ubicado en la raiz, mismo nivel que `manage.py`. El archivo .env no se sube al repositorio git, está incluido en el .gitignore para no exponer las credenciales.

Con el env cargado la estructura se levanta con:
```
python manage.py migrate
```

# Roles y control de acceso

El usuario hereda de `AbstractUser` y agrega el campo `rol` con tres valores: `cliente`, `mesero` y `admin`.

Cada rolo tiene su propio decorador en `panel/decorators.py` (`cliente_required`, `meser_required`, `admin_required`) de manera que si un usuario autenticado con el rol equivocado intenta entrar a una ruta que no debería este recibirá un `403`, prohibiendole accesos indebidos de forma explicita.

# Panel de administración
Además del admin nativo, el proyecto tiene un panel propio en `/admin/`, construido con sus propias vistas y plantillas que incluyen el decorador `admin_required` para poder acceder. Desde allí un administrador puede:

-Gestionar la carta: crear, editar, retirar y reactivar platos.
-Gestionar alérgenos, que son el origen de los tags del menú publico.
-Gestionar mesas: crear, mover redimensionar el salón y retirar/activar mesas.
-Dar de alta a meseros y administradores. 
-Revisar y cancelar reservas
-Desactivar y reactivar clientes.

Todas las bajas son con *soft-delete*: retirar un plato, mesa, cliente, mesero no lo elimina solamente lo saca de servicio. Sin borrar trazabilidad.


# Django-admin
Igualmente, creamos un superusuario y añadimos los modelos al django-admin.

Cabe nombrar que crear un superusuario hace que este nazca con el rol='cliente' y nuestros decoradores de 'admin_required' exige rol=ADMIN asi que el superusuario servirá solo para /django-admin/ pero no para nuestro panel propio de administración.

Para lograr que el superusuario sea compatible con nuestro panel de adminstración personalizado se debe cambiar su rol desde panel.User en django-admin o en su defecto cambiarlo con el comando:

```
python manage.py shell -c "from panel.models import User;u=User.objects.get(username='TU_USERNAME'); u.rol=User.Rol.ADMIN; u.save(update_fields=['rol'])"
```

