from django import forms
from django.utils.text import slugify

from booking.models import Mesa
from menu.models import Alergeno, Item

from .models import User


class ItemForm(forms.ModelForm):
    """Alta/edicion de un plato.

    'disponible' no se expone: el retiro y la reactivacion son acciones
    explicitas (Item.retirar / Item.reactivar), no un checkbox del form.
    """

    class Meta:
        model = Item
        fields = ['nombre', 'descripcion', 'precio', 'categoria', 'badge', 'imagen', 'alergenos']
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'alergenos': forms.CheckboxSelectMultiple(),
        }


class AlergenoForm(forms.ModelForm):
    """Alta de un alergeno. El slug se deriva del nombre: no se expone al
    administrador ni se edita, porque es el valor que el frontend usa en
    data-alergeno."""

    class Meta:
        model = Alergeno
        fields = ['nombre']

    def save(self, commit=True):
        alergeno = super().save(commit=False)
        alergeno.slug = slugify(alergeno.nombre)
        if commit:
            alergeno.save()
        return alergeno


class MesaForm(forms.ModelForm):
    """Alta de una mesa. El numero se auto-asigna (Mesa.siguiente_numero);
    'activa' no se expone: retirar/reactivar son acciones explicitas."""

    class Meta:
        model = Mesa
        fields = ['capacidad', 'ubicacion', 'es_grande']

    def save(self, commit=True):
        mesa = super().save(commit=False)
        if not mesa.numero:
            mesa.numero = Mesa.siguiente_numero()
        if commit:
            mesa.save()
        return mesa


class UsuarioForm(forms.Form):
    """Campos comunes del alta de personal (meseros y administradores).

    El rol nunca viaja en el form: el servidor lo impone con la via
    controlada (User.crear_mesero / User.crear_admin), que es la que evita
    el escalado de privilegios.
    """

    email = forms.EmailField(label='Email')
    nombre = forms.CharField(max_length=150, label='Nombre')
    telefono = forms.CharField(max_length=20, required=False, label='Teléfono')
    password = forms.CharField(widget=forms.PasswordInput, label='Contraseña')
    password2 = forms.CharField(widget=forms.PasswordInput, label='Repetir contraseña')

    def clean(self):
        datos = super().clean()
        password = datos.get('password')
        password2 = datos.get('password2')
        if password and password2 and password != password2:
            raise forms.ValidationError('Las contraseñas no coinciden.')
        return datos


class MeseroForm(UsuarioForm):
    """Alta de un mesero."""

    def crear_mesero(self):
        return User.crear_mesero(
            username=self.cleaned_data['email'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data['nombre'],
            telefono=self.cleaned_data['telefono'],
        )


class AdminForm(UsuarioForm):
    """Alta de un administrador."""

    def crear_admin(self):
        return User.crear_admin(
            username=self.cleaned_data['email'],
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password'],
            first_name=self.cleaned_data['nombre'],
            telefono=self.cleaned_data['telefono'],
        )


class ClienteForm(forms.ModelForm):
    """Edicion de datos de contacto de un cliente. El email (que es el
    username) no se toca: es su credencial de acceso."""

    class Meta:
        model = User
        fields = ['first_name', 'telefono']
