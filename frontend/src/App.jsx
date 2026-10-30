
function TrackingPage({ orders, orderNumber, setOrderNumber, onBack }) {
  const [lookup, setLookup] = useState(orderNumber);
  const order = orders.find(
    (item) => item.number.toLowerCase() === lookup.trim().toLowerCase()
  );
  const [searched, setSearched] = useState(false);

  return (
    <section className="subpage tracking-page">
      <button className="back-link" onClick={onBack}>
        <ArrowLeft size={15} /> Back to orders
      </button>

      <p className="eyebrow">FROM OUR DOOR TO YOURS</p>
      <h1>Track your <em>order.</em></h1>
      <p className="subpage-intro">
        Enter your order reference to see its latest status.
      </p>

      <form
        className="tracking-form"
        onSubmit={(e) => {
          e.preventDefault();
          setOrderNumber(lookup);
          setSearched(true);
        }}
      >
        <label>
          Order reference
          <input
            value={lookup}
            onChange={(e) => setLookup(e.target.value)}
            placeholder="e.g. LM12345678"
          />
        </label>
        <button className="dark-button" type="submit">
          Track order <ArrowRight size={15} />
        </button>
      </form>

      {searched && !order && (
        <p className="tracking-message">
          We couldn't find that order in this browser. Check the number or view your orders.
        </p>
      )}

      {order && (
        <div className="tracking-result">
          <div className="tracking-result-head">
            <div>
              <p className="eyebrow">ORDER {order.number}</p>
              <h2>{order.status}</h2>
              <p>Placed on {order.date}</p>
            </div>
            <span className="status-pill">
              <span />
              In progress
            </span>
          </div>

          <div className="tracking-timeline">
            {order.timeline.map((stage, index) => (
              <div
                key={stage}
                className={`timeline-step ${index === 0 ? 'timeline-done' : ''}`}
              >
                <span className="timeline-dot">
                  {index === 0 ? <Check size={13} /> : index + 1}
                </span>
                <div>
                  <strong>{stage}</strong>
                  <small>
                    {index === 0
                      ? order.date
                      : index === 1
                      ? 'Up next'
                      : 'Awaiting update'}
                  </small>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!orders.length && !searched && (
        <div className="tracking-help">
          <CircleHelp size={19} />
          <p>
            Placed a order? Its order reference will be available on the My Orders page.
          </p>
        </div>
      )}
    </section>
  );
}
function Footer({ onNavigate, onShop }) { return <footer className="site-footer"><div className="footer-main"><div className="footer-brand-col"><button className="brand-mark footer-logo" onClick={() => onNavigate('home')}>FASHION<span> STORE</span></button><p>Thoughtful pieces for living beautifully, every day.</p><div className="social-line"><button aria-label="Instagram"><Instagram size={17} /></button><button aria-label="Help"><CircleHelp size={17} /></button></div></div><div><h3>EXPLORE</h3>{['New arrivals', 'Men', 'Women', 'Kids', 'Accessories', 'Beauty'].map((item) => <button key={item} onClick={() => onShop(item === 'New arrivals' ? 'All Products' : item)}>{item}</button>)}</div><div><h3>YOUR ACCOUNT</h3>{[['Profile', 'Profile'], ['My orders', 'Orders'], ['Track an order', 'Track order'], ['Wishlist', 'Wishlist'], ['My bag', 'Bag']].map(([text, page]) => <button key={text} onClick={() => onNavigate(page.toLowerCase() === 'track order' ? 'tracking' : page.toLowerCase())}>{text}</button>)}</div><div className="footer-help"><h3>HERE TO HELP</h3><p>Monday – Saturday<br />10:00 am – 6:00 pm IST</p><a href="mailto:hello@luxe.example">hello@luxe.example</a><p className="footer-delivery"><Truck size={15} /> Free delivery over ₹1,999</p></div></div><div className="footer-bottom"><span>© 2026 FASHION STORE. ALL RIGHTS RESERVED.</span><span>MADE WITH CARE, WORN WITH LOVE.</span><span>INDIA · INR ₹</span></div></footer>; }

export default App;
