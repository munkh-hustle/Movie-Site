document.addEventListener('DOMContentLoaded', async () => {
    await loadMovieData();
    
    // Display newest BL movies (already sorted by date_added in getMoviesByCategory)
    const blMoviesContainer = document.getElementById('bl-movies');
    const blMovies = getMoviesByCategory('bl').slice(0, 5);
    blMoviesContainer.innerHTML = blMovies.map(createMovieCard).join('');
    
    // Display newest GL movies
    const glMoviesContainer = document.getElementById('gl-movies');
    const glMovies = getMoviesByCategory('gl').slice(0, 5);
    glMoviesContainer.innerHTML = glMovies.map(createMovieCard).join('');

});