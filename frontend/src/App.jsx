import './App.css';


function App(){
  return(
    <div className="homepage">
      <div className="navbar">
        <div id="cool-stride">CoolStride</div>
        <p id="home">Home</p>
        <p id="abouthead">About</p>
        <button>Try CoolStride</button>
      </div>
      <div className="tagline">
         <p id="tag1">Find your shade.</p>
         <br></br>
         <p id="tag2"> Find your <i style={{color:"#157f47"}}>way</i>.</p>
      </div>
      <div className="about_section">
        
        <div id="about_card">The world is getting hotter, and the way we navigate should evolve with it. Every journey comes with choices, but choosing a route shouldn't just be about saving time or distance. It should be about travelling smarter.
CoolStride brings environmental awareness into everyday navigation, helping you look beyond the usual route and discover a more comfortable way forward.</div>
      </div>
      <button id="button">Try  CoolStride</button>
    </div>
  );
}

export default App;