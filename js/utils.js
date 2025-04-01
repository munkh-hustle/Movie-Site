// Shared utility functions

let movieData = {};

// Load movie data from JSON
async function loadMovieData() {
    try {
        const response = await fetch('movie-details.json');
        movieData = await response.json();
        return movieData;
    } catch (error) {
        console.error('Error loading movie data:', error);
        return {};
    }
}

// Get movies by category
function getMoviesByCategory(category) {
    return Object.values(movieData).filter(movie => 
        movie.category.toLowerCase() === category.toLowerCase()
    );
}

// Get newest movies
function getNewestMovies(limit = 5) {
    const allMovies = Object.values(movieData);
    return allMovies
        .sort((a, b) => new Date(b.release) - new Date(a.release))
        .slice(0, limit);
}

// Create movie card HTML
function createMovieCard(movie) {
    return `
        <div class="movie-card">
            <a href="movie.html?title=${encodeURIComponent(movie.title)}">
                <img src="${movie.poster}" alt="${movie.title_name || movie.title}">
                <div class="movie-info">
                    <h3>${movie.title_name || movie.title}</h3>
                    <div class="movie-meta">
                        <span>${movie.year}</span>
                        <span>${movie.rating} <i class="fas fa-star"></i></span>
                    </div>
                </div>
            </a>
        </div>
    `;
}


// Get URL parameter
function getUrlParameter(name) {
    name = name.replace(/[[]/, '\\[').replace(/[\]]/, '\\]');
    const regex = new RegExp('[\\?&]' + name + '=([^&#]*)');
    const results = regex.exec(location.search);
    return results === null ? '' : decodeURIComponent(results[1].replace(/\+/g, ' '));
}