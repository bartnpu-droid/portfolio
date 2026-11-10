<?php
/**
 * Scent notes block: a three-row list on product pages, one quiet line on product cards.
 *
 * @package Ombra\StoreTools
 *
 * @var array    $attributes Block attributes.
 * @var WP_Block $block      Block instance (context: postId).
 */

use Ombra\StoreTools\Product_Fields;

defined( 'ABSPATH' ) || exit;

$ombra_product_id = (int) ( $block->context['postId'] ?? get_the_ID() );
$ombra_notes      = $ombra_product_id ? Product_Fields::notes( $ombra_product_id ) : array();
if ( ! $ombra_notes ) {
	return;
}

$ombra_variant = ( $attributes['variant'] ?? 'full' ) === 'line' ? 'line' : 'full';
$ombra_wrapper = get_block_wrapper_attributes( array( 'class' => 'ombra-notes-block ombra-notes-block--' . $ombra_variant ) );

if ( 'line' === $ombra_variant ) {
	$ombra_line = array_filter( array( $ombra_notes['top'] ?? '', $ombra_notes['base'] ?? '' ) );
	if ( ! $ombra_line ) {
		return;
	}
	printf(
		'<p %1$s>%2$s</p>',
		$ombra_wrapper, // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- escaped by get_block_wrapper_attributes().
		esc_html( implode( ' · ', $ombra_line ) )
	);
	return;
}

$ombra_labels = array(
	'top'   => __( 'Top', 'ombra-store-tools' ),
	'heart' => __( 'Heart', 'ombra-store-tools' ),
	'base'  => __( 'Base', 'ombra-store-tools' ),
	'burn'  => __( 'Burn time', 'ombra-store-tools' ),
	'wax'   => __( 'Made with', 'ombra-store-tools' ),
);
?>
<dl <?php echo $ombra_wrapper; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- escaped by get_block_wrapper_attributes(). ?>>
	<?php foreach ( $ombra_labels as $ombra_key => $ombra_label ) : ?>
		<?php if ( ! empty( $ombra_notes[ $ombra_key ] ) ) : ?>
			<div class="ombra-notes-block__row ombra-notes-block__row--<?php echo esc_attr( $ombra_key ); ?>">
				<dt><?php echo esc_html( $ombra_label ); ?></dt>
				<dd><?php echo esc_html( $ombra_notes[ $ombra_key ] ); ?></dd>
			</div>
		<?php endif; ?>
	<?php endforeach; ?>
</dl>
