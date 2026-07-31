import React, { Component } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import ListPage from "./ListPage";
import RunPage from "./RunPage";
import { handleError } from "./utils";

class App extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="max-w-3xl mx-auto my-4 font-mono">
          Oops - there has been an error. It has been logged to the console.
        </div>
      );
    }
    return (
      <BrowserRouter>
        <div className="h-full font-mono">
          <Routes>
            <Route exact path="/" element={<ListPage />} />
            <Route path="/run/:slug" element={<RunPage />} />
            <Route path="/run" element={<RunPage />} />
          </Routes>
        </div>
      </BrowserRouter>
    );
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ error });
    handleError(error, errorInfo);
  }
}

export default App;
