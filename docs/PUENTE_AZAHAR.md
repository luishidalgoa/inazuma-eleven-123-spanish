# Puente servidor ↔ PC Windows para probar en Azahar

El proyecto y el agente viven en el servidor Linux; el emulador (Azahar) corre en un PC Windows. El
servidor entra al PC por SSH (alias `pc`), así que el agente lee los logs del emulador, deja el mod de
la traducción en `load/mods` y hace capturas sin copiar nada a mano. Sigue el flujo de `AGENTS.md`: el
usuario juega y el agente solo observa; nada envía entradas al emulador. Seguimiento: issue #117.

## Montaje (una sola vez)

- **En el servidor:** clave sin contraseña `~/.ssh/id_ed25519_pc` y esta entrada en `~/.ssh/config`:

  ```
  Host pc
      HostName <IP del PC>
      User <usuario de Windows>
      IdentityFile ~/.ssh/id_ed25519_pc
      IdentitiesOnly yes
  ```

- **En el PC (PowerShell como administrador):** instalar y arrancar el servidor OpenSSH
  (`Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0`, `Start-Service sshd`,
  `Set-Service sshd -StartupType Automatic`), poner PowerShell como shell
  (`HKLM:\SOFTWARE\OpenSSH\DefaultShell`) y añadir la clave pública de `id_ed25519_pc.pub` a
  `%ProgramData%\ssh\administrators_authorized_keys` (permisos solo para Administrators y SYSTEM).

La IP del PC cambia si el router usa DHCP: reservarla en el router, o el alias deja de funcionar.

## Operaciones habituales

- **Leer el log de Azahar:** `ssh pc 'Get-Content "$env:APPDATA\Azahar\log\azahar_log.txt" -Tail 80'`
  (el de la sesión anterior es `azahar_log.old.txt`).
- **Traer capturas o ficheros:** `scp pc:'C:/Users/<usuario>/AppData/Roaming/Azahar/screenshots/*' <destino>`.
- **¿Azahar abierto?** `ssh pc 'Get-Process azahar -ErrorAction SilentlyContinue'`.
- **Depurador (stub GDB de Azahar):** activar «Habilitar stub GDB» en la configuración de Azahar y abrir un
  túnel, sin regla de firewall: `ssh -N -L 24689:127.0.0.1:24689 pc`; luego `gdb-multiarch` con
  `target remote 127.0.0.1:24689`. El túnel no se ha probado todavía. El stub solo existe con un juego
  cargado, y los puntos de parada deben ponerse con el CRO ya cargado.

## Instalar la traducción (release v3.0) en el emulador

Se usa el instalador de la release sobre la ROM japonesa 1.0 y la CIA de la 1.4 del usuario, que están
en `%APPDATA%\Azahar\roms` del PC. Todo se descarga en una carpeta temporal de `work/shared/releases/`
y se borra al terminar.

1. `gh release download v3.0 --pattern 'inazuma123-es-v3.0-luma.zip' --pattern SHA256SUMS.txt` y
   comprobar el sha256 contra `SHA256SUMS.txt`.
2. Traer ROM y CIA al servidor con `scp` y ejecutar su `instalar.py` (necesita `xdelta3`):

   ```bash
   python3 -I -X utf8 instalar.py --version 1.4 --destino azahar \
     --juego <rom>.3ds --actualizacion update_v1.4.0.cia --salida <carpeta temporal> --sin-pausa
   ```

   El instalador comprueba el sha256 de cada original y de cada resultado.
3. Con Azahar cerrado, copiar `<salida>/azahar/load/mods/00040000000BB800/romfs/` al PC
   (`scp -r`, hacia `%APPDATA%\Azahar\load\mods\00040000000BB800\romfs`) y comparar sha256 de
   origen y destino.
4. Borrar la carpeta temporal y las copias de ROM del servidor.

Una candidata nueva se prepara con `instalar.azahar(candidata, raiz_mods=...)` de
`ie123kit.nucleo.construir.instalar` (o con `ServicioToolkit.instalar`). Antes de copiar nada, `azahar` comprueba que
`usearch.dat` corresponde al `unitbase.dat` de la candidata (hook de nombres de jugador; `docs/HARNESS.md` §4) y se
niega si no; el opt-out nombrado `comprobar_sincronia_usearch=False` es solo para tests. Un `archive.fa` obtenido por la
cadena en sitio (`apply.py`) o por `build_ui_revision.py` (congelado, sin el paso) se cierra antes con
`python -X utf8 -m ie123kit.servicio.sincronia_usearch cerrar <copia>`; la copia manual con `scp` no pasa por esa
comprobación, así que se hace `... sincronia_usearch verificar <archive.fa>` (código 0) antes del `scp`. La carpeta `probe_ie3_fuego_v17` por sí sola no es instalable
(las CRO están sueltas y el audio salió del mod ya instalado).

## Límites y seguridad

- Quien tenga acceso al servidor tiene acceso de administrador al PC (la clave no lleva contraseña).
  Convención: el agente escribe en el PC solo bajo `%APPDATA%\Azahar` y no toca nada fuera.
- El servidor comparte `Cache` a invitados con escritura para toda la red local
  (`/etc/samba/smb.conf`); conviene restringirlo si la red no es de confianza.
