document.addEventListener('DOMContentLoaded', async () => {
    await loadMovieData();
    
    // Display newest BL movies (already sorted by date_added in getMoviesByCategory)
    const blMoviesContainer = document.getElementById('bl-movies');
    const blMovies = getMoviesByCategory('movielex').slice(0, 8);
    blMoviesContainer.innerHTML = blMovies.map(createMovieCard).join('');

});
