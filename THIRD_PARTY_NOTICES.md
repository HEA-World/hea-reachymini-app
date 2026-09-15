# Third-party notices

This app depends on the following Pollen Robotics projects, which are licensed
under Apache License 2.0:

- `pollen-robotics/reachy_mini`, used through `reachy-mini==1.10.0`;
- `pollen-robotics/reachy-mini-emotions-library`, read at pinned revision
  `873ae49f0b89114b7e535eff0c1f7560d21d9357` through the Reachy SDK.

No Pollen motion trajectory is copied into this source package. At runtime the
SDK obtains the official recordings and the app selects only locally allowlisted
recording identifiers. Recording audio is disabled.

`requests==2.34.2` is licensed under Apache License 2.0. Transitive dependency
licenses remain those distributed by their respective projects.
