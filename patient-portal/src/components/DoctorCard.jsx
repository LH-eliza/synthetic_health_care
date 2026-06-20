export default function DoctorCard({ doctor, inline = false }) {
  if (inline) {
    return (
      <div className="doctor-inline">
        <p className="doctor-inline__note">&ldquo;{doctor.note}&rdquo;</p>
        <p className="doctor-inline__contact">
          {doctor.contact.phone} · {doctor.contact.email}
        </p>
      </div>
    );
  }

  return (
    <section className="card doctor-card">
      <div className="doctor-card__header">
        <div className="doctor-card__avatar">{doctor.initials}</div>
        <div>
          <div className="doctor-card__name">{doctor.name}</div>
          <div className="doctor-card__meta">{doctor.specialty} · {doctor.clinicName}</div>
        </div>
      </div>
      <p className="doctor-card__note">{doctor.note}</p>
    </section>
  );
}
